from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crater.domain.watermark import HighWaterMark
from crater.infrastructure.redis.watermark_store import InMemoryWatermarkStore


def dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


class TestInMemoryWatermarkStore:
    @pytest.mark.asyncio
    async def test_get_returns_none_initially(self):
        store = InMemoryWatermarkStore()
        assert await store.get() is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        store = InMemoryWatermarkStore()
        wm = HighWaterMark(last_ingested_hour=dt("2024-01-15T05:00:00"))
        await store.set(wm)
        result = await store.get()
        assert result is not None
        assert result.last_ingested_hour == dt("2024-01-15T05:00:00")

    @pytest.mark.asyncio
    async def test_set_if_greater_advances_when_greater(self):
        store = InMemoryWatermarkStore()
        await store.set(HighWaterMark(last_ingested_hour=dt("2024-01-15T04:00:00")))
        advanced = await store.set_if_greater(dt("2024-01-15T05:00:00"))
        assert advanced is True
        result = await store.get()
        assert result.last_ingested_hour == dt("2024-01-15T05:00:00")

    @pytest.mark.asyncio
    async def test_set_if_greater_does_not_advance_when_equal_or_less(self):
        store = InMemoryWatermarkStore()
        await store.set(HighWaterMark(last_ingested_hour=dt("2024-01-15T05:00:00")))
        advanced = await store.set_if_greater(dt("2024-01-15T03:00:00"))
        assert advanced is False
        result = await store.get()
        assert result.last_ingested_hour == dt("2024-01-15T05:00:00")

    @pytest.mark.asyncio
    async def test_set_if_greater_works_from_none(self):
        store = InMemoryWatermarkStore()
        advanced = await store.set_if_greater(dt("2024-01-15T00:00:00"))
        assert advanced is True
