from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

from crater.domain.models import PushCommitRecord
from crater.infrastructure.postgres.repositories.base import AbstractRepository

log = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO push_commits
    (event_id, repo_id, repo_name, pusher_login, author_name,
     author_email, sha, forced, pushed_at)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""


class PushCommitRepository(AbstractRepository[PushCommitRecord]):
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def bulk_insert(self, records: list[PushCommitRecord]) -> int:
        if not records:
            return 0
        rows = [
            (
                r.event_id, r.repo_id, r.repo_name, r.pusher_login,
                r.author_name, r.author_email, r.sha, r.forced, r.pushed_at,
            )
            for r in records
        ]
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(_INSERT_SQL, rows)
            await conn.commit()
        return len(rows)
