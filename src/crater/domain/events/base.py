from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crater.domain.models import (
        ContributionRecord,
        NormalizedEvent,
        PushCommitRecord,
        RawEvent,
    )


class AbstractEventNormalizer(ABC):
    """Strategy contract for per-event-type normalization.

    Each concrete subclass handles exactly one GitHub event type. The registry
    dispatches to the correct subclass at runtime; unknown types fall back to
    UnknownEventNormalizer so no event is ever dropped.
    """

    @property
    @abstractmethod
    def event_type(self) -> str:
        """The GitHub event type string this normalizer handles, e.g. 'PushEvent'."""

    @abstractmethod
    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        """Extract a flat NormalizedEvent from the raw envelope."""

    def extract_commits(self, raw: RawEvent) -> list[PushCommitRecord]:
        """Extract commit-level records. Only PushEventNormalizer overrides this."""
        return []

    def extract_contributions(self, raw: RawEvent) -> list[ContributionRecord]:
        """Extract (actor, repo, type) contribution records for Q3/Q5.

        Both PushEventNormalizer and PullRequestEventNormalizer override this.
        Other types contribute nothing to the graph.
        """
        return []


class EventNormalizerRegistry:
    """Strategy dispatcher: maps event type strings to normalizer instances.

    Usage:
        registry = EventNormalizerRegistry.build_default()
        normalizer = registry.get("PushEvent")
        result = normalizer.normalize(raw_event)
    """

    def __init__(self) -> None:
        self._normalizers: dict[str, AbstractEventNormalizer] = {}
        self._unknown: AbstractEventNormalizer | None = None

    def register(self, normalizer: AbstractEventNormalizer) -> None:
        self._normalizers[normalizer.event_type] = normalizer

    def set_unknown_fallback(self, normalizer: AbstractEventNormalizer) -> None:
        self._unknown = normalizer

    def get(self, event_type: str) -> AbstractEventNormalizer:
        if normalizer := self._normalizers.get(event_type):
            return normalizer
        if self._unknown is not None:
            return self._unknown
        raise KeyError(f"No normalizer registered for '{event_type}' and no fallback set")

    @classmethod
    def build_default(cls) -> EventNormalizerRegistry:
        from crater.domain.events.push import PushEventNormalizer
        from crater.domain.events.pull_request import PullRequestEventNormalizer
        from crater.domain.events.watch import WatchEventNormalizer
        from crater.domain.events.fork import ForkEventNormalizer
        from crater.domain.events.issues import IssuesEventNormalizer
        from crater.domain.events.issue_comment import IssueCommentEventNormalizer
        from crater.domain.events.create import CreateEventNormalizer
        from crater.domain.events.delete import DeleteEventNormalizer
        from crater.domain.events.release import ReleaseEventNormalizer
        from crater.domain.events.unknown import UnknownEventNormalizer

        registry = cls()
        for normalizer in (
            PushEventNormalizer(),
            PullRequestEventNormalizer(),
            WatchEventNormalizer(),
            ForkEventNormalizer(),
            IssuesEventNormalizer(),
            IssueCommentEventNormalizer(),
            CreateEventNormalizer(),
            DeleteEventNormalizer(),
            ReleaseEventNormalizer(),
        ):
            registry.register(normalizer)

        registry.set_unknown_fallback(UnknownEventNormalizer())
        return registry
