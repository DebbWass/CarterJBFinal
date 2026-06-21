from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from crater.config.settings import PipelineSettings
from crater.domain.watermark import HighWaterMark
from crater.infrastructure.redis.watermark_store import InMemoryWatermarkStore
from crater.pipeline.poller import HourPoller


def dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def make_poller(watermark_store, sim_now: datetime) -> HourPoller:
    settings = PipelineSettings(
        vendor_base_url="http://fake",
        pg_dsn="postgresql://x:x@x/x",
        redis_url="redis://x",
        replay_window_start=date(2024, 1, 15),
        replay_window_end=date(2024, 1, 21),
    )
    vendor_client = AsyncMock()
    vendor_client.get_simulated_now = AsyncMock(return_value=sim_now)
    return HourPoller(watermark_store, vendor_client, settings)


class TestHourPoller:
    @pytest.mark.asyncio
    async def test_returns_first_file_when_no_watermark(self):
        store = InMemoryWatermarkStore()
        poller = make_poller(store, sim_now=dt("2024-01-15T02:00:00"))
        filename = await poller.next_filename()
        assert filename == "2024-01-15-0.json.gz"

    @pytest.mark.asyncio
    async def test_returns_none_when_sim_clock_not_reached(self):
        store = InMemoryWatermarkStore()
        poller = make_poller(store, sim_now=dt("2024-01-15T00:30:00"))
        filename = await poller.next_filename()
        assert filename is None

    @pytest.mark.asyncio
    async def test_advances_past_watermark(self):
        store = InMemoryWatermarkStore()
        await store.set(HighWaterMark(last_ingested_hour=dt("2024-01-15T02:00:00")))
        poller = make_poller(store, sim_now=dt("2024-01-15T04:00:00"))
        filename = await poller.next_filename()
        assert filename == "2024-01-15-3.json.gz"

    @pytest.mark.asyncio
    async def test_returns_none_at_window_end(self):
        store = InMemoryWatermarkStore()
        await store.set(HighWaterMark(last_ingested_hour=dt("2024-01-20T23:00:00")))
        poller = make_poller(store, sim_now=dt("2024-01-21T05:00:00"))
        filename = await poller.next_filename()
        assert filename is None

    @pytest.mark.asyncio
    async def test_filename_not_zero_padded(self):
        store = InMemoryWatermarkStore()
        await store.set(HighWaterMark(last_ingested_hour=dt("2024-01-15T00:00:00")))
        poller = make_poller(store, sim_now=dt("2024-01-15T02:30:00"))
        filename = await poller.next_filename()
        assert filename == "2024-01-15-1.json.gz"
        assert "01" not in filename.split("-")[3]
