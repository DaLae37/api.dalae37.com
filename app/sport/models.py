from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class Team(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str


class Standing(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int
    played: int
    wins: int
    draws: int
    losses: int
    win_rate: float | None = None
    games_behind: float | None = None
    points: int | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    goal_difference: int | None = None


class NextGame(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    start_time: time
    opponent: str
    home: bool
    venue: str

    @field_validator("start_time")
    @classmethod
    def require_aware_time(cls, value: time) -> time:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_time must include a UTC offset")
        return value


class TeamSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    sport: Literal["baseball", "football"]
    league: str
    team: Team
    standing: Standing
    next_game: NextGame | None
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must be timezone-aware")
        return value
