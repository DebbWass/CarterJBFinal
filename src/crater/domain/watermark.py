from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class HighWaterMark:
    """Value object: the last hour successfully ingested into Postgres."""

    last_ingested_hour: datetime

    def advance(self, next_hour: datetime) -> HighWaterMark:
        if next_hour <= self.last_ingested_hour:
            raise ValueError(
                f"Cannot advance watermark backwards: {next_hour} <= {self.last_ingested_hour}"
            )
        return HighWaterMark(last_ingested_hour=next_hour)

    def next_hour(self) -> datetime:
        return self.last_ingested_hour + timedelta(hours=1)

    def next_filename(self) -> str:
        """Return the filename for the next un-ingested hour.

        GH Archive convention: hour segment is NOT zero-padded.
        E.g. 2024-01-15T03:00Z → '2024-01-15-3.json.gz'
            2024-01-15T13:00Z → '2024-01-15-13.json.gz'
        """
        dt = self.next_hour()
        return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}-{dt.hour}.json.gz"

    @staticmethod
    def hour_to_filename(hour: datetime) -> str:
        """Convert an arbitrary sim-hour datetime to its vendor filename."""
        return f"{hour.year:04d}-{hour.month:02d}-{hour.day:02d}-{hour.hour}.json.gz"

    @staticmethod
    def filename_to_hour(filename: str) -> datetime:
        """Parse a vendor filename back to its UTC sim-hour datetime."""
        stem = filename.removesuffix(".json.gz")
        parts = stem.split("-")
        year, month, day, hour = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        return datetime(year, month, day, hour, tzinfo=timezone.utc)
