from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

from app.core.exceptions import (
    ProviderDataNotFoundError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnexpectedProviderResponseError,
)


KBO_BASE_URL = "https://www.koreabaseball.com"
KBO_STANDINGS_PATH = "/Record/TeamRank/TeamRankDaily.aspx"
KBO_SCHEDULE_PATH = "/ws/Schedule.asmx/GetScheduleList"
KBO_LEAGUE_ID = "1"
KBO_REGULAR_SERIES_IDS = "0,9,6"

SAMSUNG_LIONS_TEAM_ID = "SS"
SAMSUNG_LIONS_PROVIDER_NAME = "삼성"
SAMSUNG_LIONS_NAME = "삼성 라이온즈"


@dataclass(frozen=True, slots=True)
class KBOStandingData:
    rank: int
    played: int
    wins: int
    draws: int
    losses: int
    win_rate: float
    games_behind: float


@dataclass(frozen=True, slots=True)
class KBOGameData:
    starts_at: datetime
    opponent: str
    home: bool
    venue: str


class KBOClient:
    def __init__(self, http_client: httpx.AsyncClient, timezone_info: ZoneInfo) -> None:
        self._http = http_client
        self._timezone = timezone_info

    async def get_samsung_standing(self) -> KBOStandingData:
        try:
            response = await self._http.get(f"{KBO_BASE_URL}{KBO_STANDINGS_PATH}")
            response.raise_for_status()
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise ProviderTimeoutError("KBO standings request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("KBO standings request failed") from exc

        return self.parse_samsung_standing(response.text)

    async def get_samsung_next_game(self, now: datetime) -> KBOGameData | None:
        local_now = now.astimezone(self._timezone)
        season_year = local_now.year

        for month in range(local_now.month, 13):
            payload = await self._get_schedule_month(season_year, month)
            game = self.parse_samsung_next_game(
                payload,
                season_year=season_year,
                now=local_now,
            )
            if game is not None:
                return game
        return None

    async def _get_schedule_month(self, season_year: int, month: int) -> Mapping[str, Any]:
        try:
            response = await self._http.post(
                f"{KBO_BASE_URL}{KBO_SCHEDULE_PATH}",
                data={
                    "leId": KBO_LEAGUE_ID,
                    "srIdList": KBO_REGULAR_SERIES_IDS,
                    "seasonId": str(season_year),
                    "gameMonth": f"{month:02d}",
                    "teamId": SAMSUNG_LIONS_TEAM_ID,
                },
                headers={"Referer": f"{KBO_BASE_URL}/Schedule/Schedule.aspx"},
            )
            response.raise_for_status()
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise ProviderTimeoutError("KBO schedule request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("KBO schedule request failed") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise UnexpectedProviderResponseError("KBO schedule was not JSON") from exc
        if not isinstance(payload, Mapping):
            raise UnexpectedProviderResponseError("KBO schedule root must be an object")
        return payload

    @staticmethod
    def parse_samsung_standing(html: str) -> KBOStandingData:
        soup = BeautifulSoup(html, "html.parser")
        required_headers = {"순위", "팀명", "경기", "승", "패", "무", "승률", "게임차"}

        table: Tag | None = None
        headers: list[str] = []
        for candidate in soup.find_all("table"):
            candidate_headers = [cell.get_text(strip=True) for cell in candidate.find_all("th")]
            if required_headers.issubset(candidate_headers):
                table = candidate
                headers = candidate_headers
                break

        if table is None:
            raise UnexpectedProviderResponseError("KBO standings table was not found")

        positions = {name: headers.index(name) for name in required_headers}
        body = table.find("tbody")
        if not isinstance(body, Tag):
            raise UnexpectedProviderResponseError("KBO standings body was not found")

        for row in body.find_all("tr", recursive=False):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td", recursive=False)]
            if len(cells) < len(headers):
                continue
            if cells[positions["팀명"]] != SAMSUNG_LIONS_PROVIDER_NAME:
                continue
            try:
                return KBOStandingData(
                    rank=int(cells[positions["순위"]]),
                    played=int(cells[positions["경기"]]),
                    wins=int(cells[positions["승"]]),
                    losses=int(cells[positions["패"]]),
                    draws=int(cells[positions["무"]]),
                    win_rate=float(cells[positions["승률"]]),
                    games_behind=float(cells[positions["게임차"]]),
                )
            except (ValueError, IndexError) as exc:
                raise UnexpectedProviderResponseError(
                    "KBO Samsung standings fields were invalid"
                ) from exc

        raise ProviderDataNotFoundError("Samsung Lions standings were not found")

    @classmethod
    def parse_samsung_next_game(
        cls,
        payload: Mapping[str, Any],
        *,
        season_year: int,
        now: datetime,
    ) -> KBOGameData | None:
        rows = payload.get("rows")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise UnexpectedProviderResponseError("KBO schedule rows were missing")

        candidates: list[KBOGameData] = []
        current_month_day: tuple[int, int] | None = None
        for item in rows:
            if not isinstance(item, Mapping):
                raise UnexpectedProviderResponseError("KBO schedule row was invalid")
            cells = item.get("row")
            if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)):
                raise UnexpectedProviderResponseError("KBO schedule cells were missing")
            if len(cells) < 8 or not all(isinstance(cell, Mapping) for cell in cells):
                raise UnexpectedProviderResponseError("KBO schedule cell count changed")

            texts = [str(cell.get("Text") or "") for cell in cells]
            date_match = re.search(r"(\d{2})\.(\d{2})", texts[0])
            time_match = re.search(r"(\d{2}):(\d{2})", texts[1])
            if date_match is not None:
                current_month_day = (int(date_match.group(1)), int(date_match.group(2)))
            if current_month_day is None or time_match is None:
                continue

            matchup = BeautifulSoup(texts[2], "html.parser")
            teams = [tag.get_text(strip=True) for tag in matchup.find_all("span", recursive=False)]
            if len(teams) != 2:
                raise UnexpectedProviderResponseError("KBO schedule teams were invalid")
            away_team, home_team = teams
            if SAMSUNG_LIONS_PROVIDER_NAME not in (away_team, home_team):
                continue

            try:
                starts_at = datetime(
                    season_year,
                    current_month_day[0],
                    current_month_day[1],
                    int(time_match.group(1)),
                    int(time_match.group(2)),
                    tzinfo=now.tzinfo,
                )
            except ValueError as exc:
                raise UnexpectedProviderResponseError("KBO schedule date was invalid") from exc
            if starts_at < now:
                continue

            is_home = home_team == SAMSUNG_LIONS_PROVIDER_NAME
            candidates.append(
                KBOGameData(
                    starts_at=starts_at,
                    opponent=away_team if is_home else home_team,
                    home=is_home,
                    venue=BeautifulSoup(texts[7], "html.parser").get_text(" ", strip=True),
                )
            )

        return min(candidates, key=lambda game: game.starts_at) if candidates else None


__all__ = [
    "KBOClient",
    "KBOGameData",
    "KBOStandingData",
    "SAMSUNG_LIONS_NAME",
    "SAMSUNG_LIONS_TEAM_ID",
]
