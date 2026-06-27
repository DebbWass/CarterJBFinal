"""Query contract test fixtures — require running Postgres.

Run with: make test-queries (starts docker services first).

Seeds deterministic fixture data (tests/queries/fixtures/seed_data.sql) once
per session; the seed script truncates affected tables first, so reruns are
safe.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest_asyncio

from crater.config.settings import PipelineSettings
from crater.infrastructure.postgres.connection import create_pool
from crater.infrastructure.postgres.migrations import SchemaMigrator

_SEED_SQL = (Path(__file__).parent / "fixtures" / "seed_data.sql").read_text()


@pytest_asyncio.fixture(scope="session")
async def settings():
    return PipelineSettings(
        pg_dsn=os.environ.get(
            "PG_DSN",
            "postgresql+psycopg://crater:crater@localhost:15432/crater",
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:16379/0"),
    )


@pytest_asyncio.fixture(scope="session")
async def pool(settings):
    p = await create_pool(settings)
    migrator = SchemaMigrator()
    await migrator.run(p)
    async with p.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_SEED_SQL)
        await conn.commit()
    yield p
    await p.close()
