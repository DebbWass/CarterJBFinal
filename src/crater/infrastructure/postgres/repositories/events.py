from __future__ import annotations

import json
import logging

from psycopg_pool import AsyncConnectionPool

from crater.domain.models import NormalizedEvent
from crater.infrastructure.postgres.repositories.base import AbstractRepository

log = logging.getLogger(__name__)

_COLUMNS = (
    "event_id",
    "event_type",
    "created_at",
    "actor_login",
    "actor_id",
    "is_bot",
    "repo_id",
    "repo_name",
    "pr_number",
    "pr_author_login",
    "pr_action",
    "pr_merged",
    "pr_language",
    "pr_base_repo_id",
    "fork_forkee_repo_id",
    "raw_payload",
)

_COPY_SQL = f"""
COPY events ({", ".join(_COLUMNS)})
FROM STDIN
WITH (FORMAT TEXT, DELIMITER '\t', NULL '\\N')
"""

_INSERT_SQL = f"""
INSERT INTO events ({", ".join(_COLUMNS)})
VALUES ({", ".join(["%s"] * len(_COLUMNS))})
ON CONFLICT (event_id) DO NOTHING
"""


class EventRepository(AbstractRepository[NormalizedEvent]):
    """Persists NormalizedEvents via psycopg3 COPY for maximum throughput.

    Falls back to a batched INSERT ON CONFLICT DO NOTHING if COPY is
    unavailable (e.g. in some test environments).
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def bulk_insert(self, records: list[NormalizedEvent]) -> int:
        if not records:
            return 0
        try:
            return await self._copy_insert(records)
        except Exception as exc:
            log.warning("COPY insert failed, falling back to batch INSERT", exc_info=exc)
            return await self._batch_insert(records)

    async def _copy_insert(self, records: list[NormalizedEvent]) -> int:
        written = 0
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                async with cur.copy(_COPY_SQL) as copy:
                    for r in records:
                        row = (
                            r.event_id,
                            r.event_type,
                            r.created_at.isoformat(),
                            r.actor_login,
                            str(r.actor_id) if r.actor_id is not None else "\\N",
                            "t" if r.is_bot else "f",
                            str(r.repo_id),
                            r.repo_name,
                            str(r.pr_number) if r.pr_number is not None else "\\N",
                            r.pr_author_login if r.pr_author_login else "\\N",
                            r.pr_action if r.pr_action else "\\N",
                            ("t" if r.pr_merged else "f") if r.pr_merged is not None else "\\N",
                            r.pr_language if r.pr_language else "\\N",
                            str(r.pr_base_repo_id) if r.pr_base_repo_id is not None else "\\N",
                            str(r.fork_forkee_repo_id) if r.fork_forkee_repo_id is not None else "\\N",
                            json.dumps(r.raw_payload),
                        )
                        await copy.write_row(row)
                        written += 1
            await conn.commit()
        return written

    async def _batch_insert(self, records: list[NormalizedEvent]) -> int:
        written = 0
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                for r in records:
                    await cur.execute(
                        _INSERT_SQL,
                        (
                            r.event_id, r.event_type, r.created_at,
                            r.actor_login, r.actor_id, r.is_bot,
                            r.repo_id, r.repo_name,
                            r.pr_number, r.pr_author_login, r.pr_action,
                            r.pr_merged, r.pr_language, r.pr_base_repo_id,
                            r.fork_forkee_repo_id,
                            json.dumps(r.raw_payload),
                        ),
                    )
                    written += 1
            await conn.commit()
        return written
