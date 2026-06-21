from __future__ import annotations

import logging

from psycopg_pool import AsyncConnectionPool

from crater.domain.models import ContributionRecord, NormalizedEvent
from crater.infrastructure.postgres.repositories.base import AbstractRepository

log = logging.getLogger(__name__)

_CONTRIBUTION_SQL = """
INSERT INTO actor_repo_contributions
    (actor_login, repo_id, repo_name, contribution_type, first_contributed)
VALUES
    (%s, %s, %s, %s, %s)
ON CONFLICT (actor_login, repo_id, contribution_type) DO NOTHING
"""

_FUNNEL_EVENTS = {"WatchEvent", "ForkEvent", "PullRequestEvent"}

_FUNNEL_SQL = """
INSERT INTO funnel_events
    (actor_login, repo_id, repo_name, event_type, occurred_at, pr_action)
VALUES
    (%s, %s, %s, %s, %s, %s)
ON CONFLICT (actor_login, repo_id, event_type, occurred_at) DO NOTHING
"""


class ContributionRepository(AbstractRepository[ContributionRecord]):
    """Manages actor_repo_contributions and funnel_events tables.

    Both tables use ON CONFLICT DO NOTHING so restart-replay is idempotent.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def bulk_insert(self, records: list[ContributionRecord]) -> int:
        if not records:
            return 0
        rows = [
            (r.actor_login, r.repo_id, r.repo_name, r.contribution_type, r.first_contributed)
            for r in records
        ]
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(_CONTRIBUTION_SQL, rows)
            await conn.commit()
        return len(rows)

    async def bulk_insert_funnel_events(self, events: list[NormalizedEvent]) -> int:
        """Insert WatchEvent, ForkEvent, PullRequestEvent rows into funnel_events."""
        rows = []
        for e in events:
            if e.event_type not in _FUNNEL_EVENTS:
                continue
            pr_action = e.pr_action if e.event_type == "PullRequestEvent" else None
            rows.append(
                (e.actor_login, e.repo_id, e.repo_name, e.event_type, e.created_at, pr_action)
            )
        if not rows:
            return 0
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(_FUNNEL_SQL, rows)
            await conn.commit()
        return len(rows)
