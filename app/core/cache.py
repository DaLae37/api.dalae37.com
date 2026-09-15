from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast


T = TypeVar("T")
_MISSING = object()


@dataclass(slots=True)
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache:
    """Small async in-memory cache with one in-flight load per key."""

    def __init__(
        self,
        ttl_seconds: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, _CacheEntry[object]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def get(self, key: str) -> object:
        entry = self._entries.get(key)
        if entry is None:
            return _MISSING
        if entry.expires_at <= self._clock():
            self._entries.pop(key, None)
            return _MISSING
        return entry.value

    async def get_or_set(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        cached = self.get(key)
        if cached is not _MISSING:
            return cast(T, cached)

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self.get(key)
            if cached is not _MISSING:
                return cast(T, cached)

            value = await loader()
            self._entries[key] = _CacheEntry(
                value=value,
                expires_at=self._clock() + self._ttl_seconds,
            )
            return value

    def clear(self) -> None:
        self._entries.clear()

