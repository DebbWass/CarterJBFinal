from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crater.domain.watermark import HighWaterMark


def dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


class TestHighWaterMark:
    def test_next_filename_non_zero_padded_hour(self):
        wm = HighWaterMark(last_ingested_hour=dt("2024-01-15T02:00:00"))
        assert wm.next_filename() == "2024-01-15-3.json.gz"

    def test_next_filename_double_digit_hour(self):
        wm = HighWaterMark(last_ingested_hour=dt("2024-01-15T12:00:00"))
        assert wm.next_filename() == "2024-01-15-13.json.gz"

    def test_next_filename_midnight(self):
        wm = HighWaterMark(last_ingested_hour=dt("2024-01-14T23:00:00"))
        assert wm.next_filename() == "2024-01-15-0.json.gz"

    def test_advance_returns_new_instance(self):
        wm = HighWaterMark(last_ingested_hour=dt("2024-01-15T00:00:00"))
        advanced = wm.advance(dt("2024-01-15T01:00:00"))
        assert wm.last_ingested_hour != advanced.last_ingested_hour
        assert advanced.last_ingested_hour == dt("2024-01-15T01:00:00")

    def test_advance_rejects_backwards(self):
        wm = HighWaterMark(last_ingested_hour=dt("2024-01-15T05:00:00"))
        with pytest.raises(ValueError):
            wm.advance(dt("2024-01-15T04:00:00"))

    def test_filename_to_hour_roundtrip(self):
        original = dt("2024-01-15T03:00:00")
        filename = HighWaterMark.hour_to_filename(original)
        recovered = HighWaterMark.filename_to_hour(filename)
        assert recovered == original

    def test_hour_to_filename_zero_padded_month_day(self):
        hour = dt("2024-01-05T09:00:00")
        assert HighWaterMark.hour_to_filename(hour) == "2024-01-05-9.json.gz"
