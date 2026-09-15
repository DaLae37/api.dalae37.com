from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from app.core.cache import TTLCache
from app.sport.models import NextGame, Standing, Team, TeamSnapshot
from app.sport.providers.kbo import KBOClient, SAMSUNG_LIONS_NAME
from app.sport.providers.kleague import FC_SEOUL_NAME, KLeagueClient


SAMSUNG_LIONS_API_ID = "samsunglions"
FC_SEOUL_API_ID = "fcseoul"


def _time_with_fixed_offset(value: datetime) -> time:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("datetime must be timezone-aware")
    return value.time().replace(tzinfo=timezone(offset))


class SportService:
    def __init__(
        self,
        *,
        kbo_client: KBOClient,
        kleague_client: KLeagueClient,
        cache: TTLCache,
        timezone_info: ZoneInfo,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._kbo = kbo_client
        self._kleague = kleague_client
        self._cache = cache
        self._timezone = timezone_info
        self._now_factory = now_factory or (lambda: datetime.now(self._timezone))

    async def get_samsung_lions(self) -> TeamSnapshot:
        return await self._cache.get_or_set("team:kbo:samsunglions", self._load_samsung_lions)

    async def get_fc_seoul(self) -> TeamSnapshot:
        return await self._cache.get_or_set("team:kleague:fcseoul", self._load_fc_seoul)

    async def _load_samsung_lions(self) -> TeamSnapshot:
        now = self._now_factory().astimezone(self._timezone)
        standing_data, game_data = await asyncio.gather(
            self._kbo.get_samsung_standing(),
            self._kbo.get_samsung_next_game(now),
        )
        next_game = None
        if game_data is not None:
            next_game = NextGame(
                date=game_data.starts_at.date(),
                start_time=_time_with_fixed_offset(game_data.starts_at),
                opponent=game_data.opponent,
                home=game_data.home,
                venue=game_data.venue,
            )

        return TeamSnapshot(
            sport="baseball",
            league="KBO",
            team=Team(id=SAMSUNG_LIONS_API_ID, name=SAMSUNG_LIONS_NAME),
            standing=Standing(
                rank=standing_data.rank,
                played=standing_data.played,
                wins=standing_data.wins,
                draws=standing_data.draws,
                losses=standing_data.losses,
                win_rate=standing_data.win_rate,
                games_behind=standing_data.games_behind,
            ),
            next_game=next_game,
            updated_at=now,
        )

    async def _load_fc_seoul(self) -> TeamSnapshot:
        now = self._now_factory().astimezone(self._timezone)
        standing_data, game_data = await asyncio.gather(
            self._kleague.get_fc_seoul_standing(now.year),
            self._kleague.get_fc_seoul_next_game(now.year, now),
        )
        next_game = None
        if game_data is not None:
            next_game = NextGame(
                date=game_data.starts_at.date(),
                start_time=_time_with_fixed_offset(game_data.starts_at),
                opponent=game_data.opponent,
                home=game_data.home,
                venue=game_data.venue,
            )

        return TeamSnapshot(
            sport="football",
            league="K League 1",
            team=Team(id=FC_SEOUL_API_ID, name=FC_SEOUL_NAME),
            standing=Standing(
                rank=standing_data.rank,
                played=standing_data.played,
                wins=standing_data.wins,
                draws=standing_data.draws,
                losses=standing_data.losses,
                points=standing_data.points,
                goals_for=standing_data.goals_for,
                goals_against=standing_data.goals_against,
                goal_difference=standing_data.goal_difference,
            ),
            next_game=next_game,
            updated_at=now,
        )
