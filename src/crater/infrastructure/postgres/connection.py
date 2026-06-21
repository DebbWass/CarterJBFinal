from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

from crater.config.settings import PipelineSettings

log = logging.getLogger(__name__)


async def create_pool(settings: PipelineSettings) -> AsyncConnectionPool:
    """Create and open a psycopg3 async connection pool."""
    dsn = settings.pg_dsn.replace("postgresql+psycopg://", "postgresql://")
    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=settings.pg_pool_min_size,
        max_size=settings.pg_pool_max_size,
        open=False,
    )
    await pool.open()
    log.info(
        "Postgres pool opened",
        extra={"min": settings.pg_pool_min_size, "max": settings.pg_pool_max_size},
    )
    return pool
