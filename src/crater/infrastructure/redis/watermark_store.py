from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import redis.asyncio as aioredis

from crater.domain.watermark import HighWaterMark
from crater.pipeline.errors import WatermarkError

log = logging.getLogger(__name__)

_SET_IF_GREATER_LUA = """
local key = KEYS[1]
local field = ARGV[1]
local new_val = ARGV[2]

local existing = redis.call('HGET', key, field)
if existing == false or existing < new_val then
    redis.call('HSET', key, field, new_val)
    return 1
end
return 0
"""


class AbstractWatermarkStore(ABC):
    @abstractmethod
    async def get(self) -> HighWaterMark | None:
        """Return the current high-water mark, or None if not yet set."""

    @abstractmethod
    async def set(self, wm: HighWaterMark) -> None:
        """Unconditionally persist the watermark."""

    @abstractmethod
    async def set_if_greater(self, hour: datetime) -> bool:
        """Atomically advance the watermark if hour > current. Returns True if advanced."""


class RedisWatermarkStore(AbstractWatermarkStore):
    """Persists the high-water mark in Redis as a HSET for O(1) reads/writes.

    set_if_greater() uses a Lua script for atomic compare-and-set to prevent
    races if the pipeline ever runs with multiple processes.
    """

    _FIELD = "last_ingested_hour"

    def __init__(self, client: aioredis.Redis, key: str = "crater:hwm") -> None:
        self._client = client
        self._key = key
        self._script = self._client.register_script(_SET_IF_GREATER_LUA)

    async def get(self) -> HighWaterMark | None:
        try:
            value = await self._client.hget(self._key, self._FIELD)
            if value is None:
                return None
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return HighWaterMark(last_ingested_hour=dt)
        except Exception as exc:
            raise WatermarkError(f"Failed to read watermark: {exc}") from exc

    async def set(self, wm: HighWaterMark) -> None:
        try:
            await self._client.hset(self._key, self._FIELD, wm.last_ingested_hour.isoformat())
        except Exception as exc:
            raise WatermarkError(f"Failed to write watermark: {exc}") from exc

    async def set_if_greater(self, hour: datetime) -> bool:
        try:
            result = await self._script(
                keys=[self._key],
                args=[self._FIELD, hour.isoformat()],
            )
            advanced = bool(result)
            if advanced:
                log.debug("Watermark advanced", extra={"hour": hour.isoformat()})
            return advanced
        except Exception as exc:
            raise WatermarkError(f"Failed to advance watermark: {exc}") from exc


class InMemoryWatermarkStore(AbstractWatermarkStore):
    """In-process test double — not safe for concurrent use."""

    def __init__(self) -> None:
        self._hour: datetime | None = None

    async def get(self) -> HighWaterMark | None:
        return HighWaterMark(last_ingested_hour=self._hour) if self._hour else None

    async def set(self, wm: HighWaterMark) -> None:
        self._hour = wm.last_ingested_hour

    async def set_if_greater(self, hour: datetime) -> bool:
        if self._hour is None or hour > self._hour:
            self._hour = hour
            return True
        return False
