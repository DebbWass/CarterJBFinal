from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

from crater.infrastructure.postgres.schema import ALL_DDL

log = logging.getLogger(__name__)


class SchemaMigrator:
    """Applies DDL idempotently at pipeline startup.

    Uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS throughout,
    so running this multiple times (e.g. after restart) is always safe.
    """

    async def run(self, pool: AsyncConnectionPool) -> None:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                for statement in ALL_DDL:
                    await cur.execute(statement)
            await conn.commit()
        log.info("Schema migration complete", extra={"statements": len(ALL_DDL)})
