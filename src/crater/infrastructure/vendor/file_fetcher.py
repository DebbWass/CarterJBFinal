from __future__ import annotations

import asyncio
import gzip
import logging
from typing import TYPE_CHECKING

from crater.pipeline.errors import GzipDecompressionError, TruncatedResponseError

if TYPE_CHECKING:
    from crater.config.settings import PipelineSettings
    from crater.infrastructure.vendor.client import VendorHttpClient
    from crater.monitoring.metrics import MetricsCollector

log = logging.getLogger(__name__)

_MAX_TRUNCATION_RETRIES = 5


class FileFetcher:
    """Manages the fetch state machine for a single vendor file.

    States and transitions:
        PENDING_CLOCK  → 404  → sleep(poll_interval) → retry
        OUTAGE         → 503  → sleep(outage_backoff * 2^n) → retry
        TRUNCATED      → gzip partial/Content-Length mismatch → immediate retry (up to N)
        READY          → 200 + valid gzip → return bytes

    Guarantees: returned bytes are valid gzip (decompressible). Callers
    can pass the result directly to FileIngestor without further validation.
    """

    def __init__(
        self,
        client: VendorHttpClient,
        settings: PipelineSettings,
        metrics: MetricsCollector,
    ) -> None:
        self._client = client
        self._poll_interval = settings.poll_interval_seconds
        self._outage_backoff = settings.outage_backoff_seconds
        self._metrics = metrics

    async def fetch_with_retry(self, filename: str) -> bytes:
        """Block until the file is successfully fetched and validated.

        Never returns truncated data. Handles all chaos modes transparently.
        """
        outage_backoff = self._outage_backoff
        truncation_attempts = 0

        while True:
            try:
                status, body = await self._client.fetch_file(filename)
            except TruncatedResponseError as exc:
                truncation_attempts += 1
                self._metrics.increment("files_truncated")
                if truncation_attempts > _MAX_TRUNCATION_RETRIES:
                    log.error(
                        "Max truncation retries exceeded",
                        extra={"gh_filename": filename, "attempts": truncation_attempts},
                    )
                    raise
                log.warning(
                    "Truncated response, retrying immediately",
                    extra={"gh_filename": filename, "attempt": truncation_attempts},
                )
                await asyncio.sleep(0.1)
                continue

            if status == 404:
                log.debug("File not ready (404)", extra={"gh_filename": filename})
                self._metrics.increment("vendor_404s")
                await asyncio.sleep(self._poll_interval)
                continue

            if status == 503:
                log.warning(
                    "Vendor outage (503), backing off",
                    extra={"gh_filename": filename, "backoff": outage_backoff},
                )
                self._metrics.increment("vendor_503s")
                await asyncio.sleep(outage_backoff)
                outage_backoff = min(outage_backoff * 2, 60.0)
                continue

            # status == 200 — validate the gzip
            assert body is not None
            if not self._is_valid_gzip(body):
                truncation_attempts += 1
                self._metrics.increment("files_truncated")
                if truncation_attempts > _MAX_TRUNCATION_RETRIES:
                    raise GzipDecompressionError(filename, Exception("gzip validation failed"))
                log.warning(
                    "Invalid gzip, retrying",
                    extra={"gh_filename": filename, "attempt": truncation_attempts},
                )
                await asyncio.sleep(0.1)
                continue

            outage_backoff = self._outage_backoff
            self._metrics.increment("files_fetched")
            log.info("File fetched successfully", extra={"gh_filename": filename, "bytes": len(body)})
            return body

    @staticmethod
    def _is_valid_gzip(data: bytes) -> bool:
        """Attempt to decompress the last chunk; returns False on truncation."""
        if len(data) < 2 or data[:2] != b"\x1f\x8b":
            return False
        try:
            gzip.decompress(data)
            return True
        except (EOFError, gzip.BadGzipFile, OSError):
            return False
