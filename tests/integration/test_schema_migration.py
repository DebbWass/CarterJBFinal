"""Verify schema migrations are idempotent."""
from __future__ import annotations

import pytest

from crater.infrastructure.postgres.migrations import SchemaMigrator


class TestSchemaMigration:
    @pytest.mark.asyncio
    async def test_migration_is_idempotent(self, pool):
        migrator = SchemaMigrator()
        await migrator.run(pool)
        await migrator.run(pool)

    @pytest.mark.asyncio
    async def test_events_table_exists(self, pool):
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='events'"
                )
                row = await cur.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_all_tables_exist(self, pool):
        expected = {"events", "push_commits", "actor_repo_contributions", "funnel_events", "pipeline_files"}
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                )
                rows = await cur.fetchall()
        found = {r[0] for r in rows}
        assert expected.issubset(found)
