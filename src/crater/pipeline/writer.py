from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from crater.domain.models import (
    ContributionRecord,
    NormalizationResult,
    NormalizedEvent,
    PushCommitRecord,
)

if TYPE_CHECKING:
    from crater.infrastructure.postgres.repositories.contributions import ContributionRepository
    from crater.infrastructure.postgres.repositories.events import EventRepository
    from crater.infrastructure.postgres.repositories.push_commits import PushCommitRepository
    from crater.monitoring.metrics import MetricsCollector

log = logging.getLogger(__name__)


@dataclass
class FlushResult:
    events_written: int = 0
    commits_written: int = 0
    contributions_written: int = 0
    funnel_events_written: int = 0


class PipelineWriter:
    """Buffers NormalizationResults and batch-flushes to Postgres.

    Buffers until `batch_size` is reached or `flush()` is called explicitly.
    flush() writes all three tables atomically (each table's writes are a single
    COPY or executemany call) before clearing the buffer.

    Restart safety: if the process crashes after DB writes but before the
    watermark advances, the next run re-inserts the same file. All tables use
    ON CONFLICT DO NOTHING / primary key deduplication, so duplicates are silently
    discarded.
    """

    def __init__(
        self,
        event_repo: EventRepository,
        commit_repo: PushCommitRepository,
        contrib_repo: ContributionRepository,
        batch_size: int,
        metrics: MetricsCollector,
    ) -> None:
        self._event_repo = event_repo
        self._commit_repo = commit_repo
        self._contrib_repo = contrib_repo
        self._batch_size = batch_size
        self._metrics = metrics

        self._events: list[NormalizedEvent] = []
        self._commits: list[PushCommitRecord] = []
        self._contributions: list[ContributionRecord] = []

    async def add(self, result: NormalizationResult) -> FlushResult | None:
        self._events.append(result.event)
        self._commits.extend(result.commits)
        self._contributions.extend(result.contributions)

        if len(self._events) >= self._batch_size:
            return await self.flush()
        return None

    async def flush(self) -> FlushResult:
        if not self._events:
            return FlushResult()

        events_to_write = self._events[:]
        commits_to_write = self._commits[:]
        contribs_to_write = self._contributions[:]

        self._events.clear()
        self._commits.clear()
        self._contributions.clear()

        try:
            e_written = await self._event_repo.bulk_insert(events_to_write)
            c_written = await self._commit_repo.bulk_insert(commits_to_write)
            co_written = await self._contrib_repo.bulk_insert(contribs_to_write)
            fe_written = await self._contrib_repo.bulk_insert_funnel_events(events_to_write)

            result = FlushResult(
                events_written=e_written,
                commits_written=c_written,
                contributions_written=co_written,
                funnel_events_written=fe_written,
            )
            self._metrics.gauge("last_flush_events", e_written)
            self._metrics.increment("total_events_written", e_written)
            self._metrics.increment("total_commits_written", c_written)
            log.info(
                "Batch flushed",
                extra={
                    "events": e_written,
                    "commits": c_written,
                    "contributions": co_written,
                    "funnel": fe_written,
                },
            )
            return result
        except Exception as exc:
            log.error("Batch flush failed", exc_info=exc)
            raise

    @property
    def pending_count(self) -> int:
        return len(self._events)
