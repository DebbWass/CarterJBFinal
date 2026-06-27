from __future__ import annotations

import asyncio
import logging

from crater.config.settings import PipelineSettings
from crater.infrastructure.redis.watermark_store import AbstractWatermarkStore
from crater.infrastructure.vendor.client import VendorHttpClient
from crater.infrastructure.vendor.file_fetcher import FileFetcher
from crater.monitoring.metrics import MetricsCollector
from crater.pipeline.ingestor import FileIngestor
from crater.pipeline.normalizer import NormalizationService
from crater.pipeline.poller import HourPoller
from crater.pipeline.writer import PipelineWriter

log = logging.getLogger(__name__)

_VENDOR_READY_POLL_SECONDS = 2.0
_VENDOR_READY_MAX_WAIT_SECONDS = 300.0


class PipelineCoordinator:
    """Top-level async orchestration loop.

    This class knows the shape of the full pipeline but contains no business
    logic itself — each step is fully delegated to a specialized component.
    It is the only class that wires: poller → fetcher → ingestor → normalizer
    → writer → watermark advance.

    Lifecycle:
        1. _wait_for_vendor()  — poll /healthz until the vendor is ready
        2. Main loop:
            a. poller.next_filename() → filename or None (sleep if None)
            b. fetcher.fetch_with_retry(filename) → gz_bytes
            c. ingestor.parse(gz_bytes) → Iterator[RawEvent]
            d. normalizer.process(event) → NormalizationResult (per event)
            e. writer.add(result) → flush if batch full
            f. writer.flush() → final flush for this file
            g. watermark_store.set_if_greater(hour) → advance HWM
        3. shutdown() → flush pending writes, cancel tasks
    """

    def __init__(
        self,
        poller: HourPoller,
        fetcher: FileFetcher,
        ingestor: FileIngestor,
        normalizer: NormalizationService,
        writer: PipelineWriter,
        watermark_store: AbstractWatermarkStore,
        metrics: MetricsCollector,
        settings: PipelineSettings,
        vendor_client: VendorHttpClient | None = None,
    ) -> None:
        self._poller = poller
        self._fetcher = fetcher
        self._ingestor = ingestor
        self._normalizer = normalizer
        self._writer = writer
        self._watermark_store = watermark_store
        self._metrics = metrics
        self._poll_interval = settings.poll_interval_seconds
        self._shutdown_event = asyncio.Event()
        self._vendor_client = vendor_client

    async def run(self) -> None:
        log.info("PipelineCoordinator starting")
        await self._wait_for_vendor()
        log.info("Vendor is ready — starting ingest loop")

        while not self._shutdown_event.is_set():
            try:
                filename = await self._poller.next_filename()
            except Exception as exc:
                log.warning("Poller error", exc_info=exc)
                await asyncio.sleep(self._poll_interval)
                continue

            if filename is None:
                await asyncio.sleep(self._poll_interval)
                continue

            try:
                await self._process_file(filename)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error(
                    "File processing failed — will retry on next poll",
                    extra={"gh_filename": filename},
                    exc_info=exc,
                )
                self._metrics.increment("file_processing_errors")
                await asyncio.sleep(self._poll_interval * 5)

        log.info("PipelineCoordinator shutting down — flushing pending writes")
        await self._writer.flush()

    async def _process_file(self, filename: str) -> None:
        log.info("Processing file", extra={"gh_filename": filename})

        gz_bytes = await self._fetcher.fetch_with_retry(filename)

        event_count = 0
        for raw in self._ingestor.parse(gz_bytes):
            result = self._normalizer.process(raw)
            await self._writer.add(result)
            event_count += 1

        await self._writer.flush()

        hour = self._poller.hour_from_filename(filename)
        await self._watermark_store.set_if_greater(hour)

        self._metrics.increment("files_ingested")
        self._metrics.gauge("last_file_event_count", event_count)
        log.info(
            "File ingested",
            extra={"gh_filename": filename, "events": event_count},
        )

    async def _wait_for_vendor(self) -> None:
        log.info("Waiting for vendor to become ready")
        waited = 0.0
        client = self._vendor_client

        while client is not None and not self._shutdown_event.is_set():
            try:
                health = await client.get_health()
                if health.get("ready"):
                    log.info("Vendor is ready", extra={"health": health})
                    return
                log.debug("Vendor not yet ready", extra={"health": health})
            except Exception as exc:
                log.debug("Vendor health check failed", exc_info=exc)

            await asyncio.sleep(_VENDOR_READY_POLL_SECONDS)
            waited += _VENDOR_READY_POLL_SECONDS
            if waited >= _VENDOR_READY_MAX_WAIT_SECONDS:
                log.warning("Vendor still not ready after %ss — proceeding anyway", waited)
                return

    async def shutdown(self) -> None:
        log.info("Shutdown signal received")
        self._shutdown_event.set()
