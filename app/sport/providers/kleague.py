from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.exceptions import (
    ProviderDataNotFoundError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnexpectedProviderResponseError,
)


KLEAGUE_BASE_URL = "https://www.kleague.com"
KLEAGUE_RANK_PATH = "/record/teamRank.do"
KLEAGUE_SCHEDULE_PATH = "/getScheduleList.do"
KLEAGUE_RANK_PAGE = f"{KLEAGUE_BASE_URL}/record/team.do"
KLEAGUE_SCHEDULE_PAGE = f"{KLEAGUE_BASE_URL}/schedule.do"
KLEAGUE_1_LEAGUE_ID = 1

FC_SEOUL_TEAM_ID = "K09"
FC_SEOUL_NAME = "FC서울"


@dataclass(frozen=True, slots=True)
class KLeagueStandingData:
    rank: int
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    goals_for: int
    goals_against: int
    goal_difference: int


@dataclass(frozen=True, slots=True)
class KLeagueGameData:
    starts_at: datetime
    opponent: str
    home: bool
    venue: str


class KLeagueClient:
    """Client for the JSON requests used by the official K League website."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        timezone_info: ZoneInfo,
    ) -> None:
        self._http = http_client
        self._timezone = timezone_info

    async def get_fc_seoul_standing(self, year: int) -> KLeagueStandingData:
        data = await self._post_data(
            KLEAGUE_RANK_PATH,
            params={
                "leagueId": str(KLEAGUE_1_LEAGUE_ID),
                "year": str(year),
                "stadium": "all",
                "recordType": "rank",
            },
            referer=KLEAGUE_RANK_PAGE,
        )
        return self.parse_fc_seoul_standing(self._required_list(data, "teamRank"))

    async def get_fc_seoul_next_game(
        self,
        year: int,
        now: datetime,
    ) -> KLeagueGameData | None:
        local_now = now.astimezone(self._timezone)
        for month in range(local_now.month, 13):
            data = await self._post_data(
                KLEAGUE_SCHEDULE_PATH,
                json_body={
                    "leagueId": KLEAGUE_1_LEAGUE_ID,
                    "teamId": FC_SEOUL_TEAM_ID,
                    "year": str(year),
                    "month": f"{month:02d}",
                    "ticketYn": "",
                },
                referer=KLEAGUE_SCHEDULE_PAGE,
            )
            game = self.parse_fc_seoul_next_game(
                self._required_list(data, "scheduleList"),
                now=local_now,
            )
            if game is not None:
                return game
        return None

    async def _post_data(
        self,
        path: str,
        *,
        referer: str,
        params: Mapping[str, str] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        headers = {
            "Accept": "application/json",
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"

        try:
            if json_body is None:
                response = await self._http.post(
                    f"{KLEAGUE_BASE_URL}{path}",
                    params=params,
                    headers=headers,
                )
            else:
                response = await self._http.post(
                    f"{KLEAGUE_BASE_URL}{path}",
                    params=params,
                    json=json_body,
                    headers=headers,
                )
            response.raise_for_status()
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise ProviderTimeoutError("K League website request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("K League website request failed") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise UnexpectedProviderResponseError(
                "K League response was not JSON"
            ) from exc

        if not isinstance(payload, Mapping):
            raise UnexpectedProviderResponseError(
                "K League response envelope was missing"
            )
        result_code = payload.get("resultCode")
        if result_code is None:
            raise UnexpectedProviderResponseError("K League resultCode was missing")
        if str(result_code) != "200":
            raise ProviderUnavailableError("K League website reported an error")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise UnexpectedProviderResponseError(
                "K League response data was missing"
            )
        return data

    @classmethod
    def parse_fc_seoul_standing(
        cls,
        items: Sequence[Mapping[str, Any]],
    ) -> KLeagueStandingData:
        for item in items:
            if str(item.get("teamId")) != FC_SEOUL_TEAM_ID:
                continue
            return KLeagueStandingData(
                rank=cls._required_int(item, "rank"),
                played=cls._required_int(item, "gameCount"),
                wins=cls._required_int(item, "winCnt"),
                draws=cls._required_int(item, "tieCnt"),
                losses=cls._required_int(item, "lossCnt"),
                points=cls._required_int(item, "gainPoint"),
                goals_for=cls._required_int(item, "gainGoal"),
                goals_against=cls._required_int(item, "lossGoal"),
                goal_difference=cls._required_int(item, "gapCnt"),
            )
        raise ProviderDataNotFoundError("FC Seoul standings were not found")

    @classmethod
    def parse_fc_seoul_next_game(
        cls,
        items: Sequence[Mapping[str, Any]],
        *,
        now: datetime,
    ) -> KLeagueGameData | None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        candidates: list[KLeagueGameData] = []
        for item in items:
            home_team_id = str(item.get("homeTeam"))
            away_team_id = str(item.get("awayTeam"))
            if FC_SEOUL_TEAM_ID not in (home_team_id, away_team_id):
                continue
            try:
                starts_at = datetime.strptime(
                    f"{cls._required_str(item, 'gameDate')} "
                    f"{cls._required_str(item, 'gameTime')}",
                    "%Y.%m.%d %H:%M",
                ).replace(tzinfo=now.tzinfo)
            except ValueError as exc:
                raise UnexpectedProviderResponseError(
                    "K League schedule date was invalid"
                ) from exc
            if starts_at < now:
                continue

            is_home = home_team_id == FC_SEOUL_TEAM_ID
            candidates.append(
                KLeagueGameData(
                    starts_at=starts_at,
                    opponent=cls._required_str(
                        item,
                        "awayTeamName" if is_home else "homeTeamName",
                    ),
                    home=is_home,
                    venue=cls._required_str(item, "fieldNameFull"),
                )
            )

        if not candidates:
            return None
        return min(candidates, key=lambda game: game.starts_at)

    @staticmethod
    def _required_list(
        data: Mapping[str, Any],
        field: str,
    ) -> list[Mapping[str, Any]]:
        items = data.get(field)
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            raise UnexpectedProviderResponseError(
                f"K League field {field} was missing or invalid"
            )
        if not all(isinstance(item, Mapping) for item in items):
            raise UnexpectedProviderResponseError(
                f"K League field {field} contained an invalid item"
            )
        return list(items)

    @staticmethod
    def _required_int(item: Mapping[str, Any], field: str) -> int:
        try:
            value = item[field]
            if value is None or isinstance(value, bool):
                raise ValueError
            return int(value)
        except (KeyError, TypeError, ValueError) as exc:
            raise UnexpectedProviderResponseError(
                f"K League field {field} was missing or invalid"
            ) from exc

    @staticmethod
    def _required_str(item: Mapping[str, Any], field: str) -> str:
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise UnexpectedProviderResponseError(
                f"K League field {field} was missing or invalid"
            )
        return value.strip()


__all__ = [
    "FC_SEOUL_NAME",
    "FC_SEOUL_TEAM_ID",
    "KLeagueClient",
    "KLeagueGameData",
    "KLeagueStandingData",
]
