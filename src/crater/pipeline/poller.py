from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from crater.domain.watermark import HighWaterMark

if TYPE_CHECKING:
    from crater.config.settings import PipelineSettings
    from crater.infrastructure.redis.watermark_store import AbstractWatermarkStore
    from crater.infrastructure.vendor.client import VendorHttpClient

log = logging.getLogger(__name__)


class HourPoller:
    """Computes the next hourly filename to fetch based on the watermark.

    Responsibilities:
    - Read the current watermark from the store.
    - Check the vendor's simulated_now to know whether the next hour is available.
    - Return None if the sim clock hasn't reached the next hour yet, so the
      caller can sleep and try again.
    - Return the filename string once the hour is reachable.

    Never fetches. Never knows about HTTP chaos. Pure scheduling logic.
    """

    def __init__(
        self,
        watermark_store: AbstractWatermarkStore,
        vendor_client: VendorHttpClient,
        settings: PipelineSettings,
    ) -> None:
        self._store = watermark_store
        self._vendor = vendor_client
        self._window_start = datetime(
            settings.replay_window_start.year,
            settings.replay_window_start.month,
            settings.replay_window_start.day,
            tzinfo=timezone.utc,
        )
        self._window_end = datetime(
            settings.replay_window_end.year,
            settings.replay_window_end.month,
            settings.replay_window_end.day,
            tzinfo=timezone.utc,
        )

    async def next_filename(self) -> str | None:
        """Return the next filename to fetch, or None if not yet available.

        Returns None when:
        - The vendor clock hasn't reached the end of the next hour.
        - The pipeline has consumed the entire replay window.
        """
        wm = await self._store.get()
        if wm is None:
            next_hour = self._window_start
        else:
            next_hour = wm.next_hour()

        if next_hour >= self._window_end:
            log.info("Replay window fully ingested", extra={"window_end": self._window_end.isoformat()})
            return None

        try:
            sim_now = await self._vendor.get_simulated_now()
        except Exception as exc:
            log.warning("Could not read simulated_now", exc_info=exc)
            return None

        from datetime import timedelta
        hour_end = next_hour + timedelta(hours=1)

        if sim_now < hour_end:
            log.debug(
                "Next hour not yet closed",
                extra={"next_hour": next_hour.isoformat(), "sim_now": sim_now.isoformat()},
            )
            return None

        filename = HighWaterMark.hour_to_filename(next_hour)
        log.debug("Next file to fetch", extra={"filename": filename})
        return filename

    def hour_from_filename(self, filename: str) -> datetime:
        return HighWaterMark.filename_to_hour(filename)
