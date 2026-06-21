"""Entry point: python -m crater

Boot sequence:
1. Load PipelineSettings from env / .env
2. Configure structured logging
3. Create Postgres connection pool + run schema migrations
4. Create Redis client + watermark store
5. Build event normalizer registry
6. Wire full object graph via constructor injection
7. Start FastAPI + uvicorn (pipeline coordinator runs as a lifespan background task)
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

import uvicorn

from crater.config.settings import PipelineSettings
from crater.infrastructure.logging.setup import configure_logging
from crater.infrastructure.postgres.connection import create_pool
from crater.infrastructure.postgres.migrations import SchemaMigrator
from crater.infrastructure.postgres.repositories.contributions import ContributionRepository
from crater.infrastructure.postgres.repositories.events import EventRepository
from crater.infrastructure.postgres.repositories.push_commits import PushCommitRepository
from crater.infrastructure.redis.connection import create_redis_client
from crater.infrastructure.redis.watermark_store import RedisWatermarkStore
from crater.infrastructure.vendor.client import VendorHttpClient
from crater.infrastructure.vendor.file_fetcher import FileFetcher
from crater.domain.events.base import EventNormalizerRegistry
from crater.monitoring.health import HealthProbe
from crater.monitoring.metrics import InMemoryMetricsCollector
from crater.pipeline.coordinator import PipelineCoordinator
from crater.pipeline.ingestor import FileIngestor
from crater.pipeline.normalizer import NormalizationService
from crater.pipeline.poller import HourPoller
from crater.pipeline.writer import PipelineWriter
from crater.api.app import create_app


async def _main() -> None:
    settings = PipelineSettings()
    configure_logging()

    log = logging.getLogger("crater.main")
    log.info("Crater pipeline starting", extra={"vendor_url": settings.vendor_base_url})

    pool = await create_pool(settings)
    migrator = SchemaMigrator()
    await migrator.run(pool)
    log.info("Schema migrations complete")

    redis_client = create_redis_client(settings)

    watermark_store = RedisWatermarkStore(redis_client, key=settings.redis_watermark_key)
    registry = EventNormalizerRegistry.build_default()
    metrics = InMemoryMetricsCollector()

    event_repo = EventRepository(pool)
    commit_repo = PushCommitRepository(pool)
    contrib_repo = ContributionRepository(pool)

    vendor_client = VendorHttpClient(settings)
    fetcher = FileFetcher(vendor_client, settings, metrics)
    ingestor = FileIngestor(metrics)
    normalizer = NormalizationService(registry, metrics)
    writer = PipelineWriter(event_repo, commit_repo, contrib_repo, settings.batch_size, metrics)
    poller = HourPoller(watermark_store, vendor_client, settings)

    coordinator = PipelineCoordinator(
        poller=poller,
        fetcher=fetcher,
        ingestor=ingestor,
        normalizer=normalizer,
        writer=writer,
        watermark_store=watermark_store,
        metrics=metrics,
        settings=settings,
        vendor_client=vendor_client,
    )

    health_probe = HealthProbe(vendor_client, pool, redis_client)
    app = create_app(coordinator, metrics, health_probe)

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )
    server = uvicorn.Server(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(coordinator.shutdown()))

    await server.serve()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
