"""Integration test fixtures — require running Postgres + Redis.

Run with: make test-integration (starts docker services first).

Postgres DSN is read from PG_DSN env var, defaulting to the compose service.
Each test class runs in a transaction that is rolled back after the test,
so tests are isolated and the database is left clean.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio

from crater.infrastructure.postgres.connection import create_pool
from crater.infrastructure.postgres.migrations import SchemaMigrator
from crater.config.settings import PipelineSettings


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
    yield p
    await p.close()
