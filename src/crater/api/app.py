from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import FastAPI

from crater.api.routes.health import router as health_router
from crater.api.routes.status import router as status_router

if TYPE_CHECKING:
    from crater.monitoring.health import HealthProbe
    from crater.monitoring.metrics import MetricsCollector
    from crater.pipeline.coordinator import PipelineCoordinator

log = logging.getLogger(__name__)


def create_app(
    coordinator: PipelineCoordinator,
    metrics: MetricsCollector,
    health_probe: HealthProbe,
) -> FastAPI:
    """FastAPI application factory.

    The pipeline coordinator runs as a background asyncio task within the
    FastAPI lifespan, so a single `uvicorn` process serves both the HTTP API
    and the ingest loop.
    """

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        log.info("Starting pipeline coordinator as background task")
        task = asyncio.create_task(coordinator.run(), name="pipeline-coordinator")
        try:
            yield
        finally:
            log.info("Lifespan ending — shutting down coordinator")
            await coordinator.shutdown()
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()

    app = FastAPI(
        title="Crater Pipeline",
        version="0.1.0",
        description="GitHub Archive talent-intelligence pipeline status API",
        lifespan=lifespan,
    )

    app.state.metrics = metrics
    app.state.health_probe = health_probe
    app.state.coordinator = coordinator

    app.include_router(health_router)
    app.include_router(status_router)

    return app
