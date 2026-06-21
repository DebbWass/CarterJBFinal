from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from crater.domain.models import NormalizationResult, RawEvent

if TYPE_CHECKING:
    from crater.domain.events.base import EventNormalizerRegistry
    from crater.monitoring.metrics import MetricsCollector

log = logging.getLogger(__name__)


class NormalizationService:
    """Routes each RawEvent to its per-type normalizer and collects results.

    Dispatches via the Strategy pattern (EventNormalizerRegistry). Unknown event
    types fall back to UnknownEventNormalizer — zero data loss.
    """

    def __init__(
        self,
        registry: EventNormalizerRegistry,
        metrics: MetricsCollector,
    ) -> None:
        self._registry = registry
        self._metrics = metrics

    def process(self, raw: RawEvent) -> NormalizationResult:
        normalizer = self._registry.get(raw.type)
        if normalizer.event_type == "__unknown__":
            self._metrics.increment("unknown_event_types")
            log.debug("Unknown event type captured", extra={"type": raw.type})

        try:
            event = normalizer.normalize(raw)
            commits = normalizer.extract_commits(raw)
            contributions = normalizer.extract_contributions(raw)
            self._metrics.increment("events_normalized")
            return NormalizationResult(
                event=event,
                commits=commits,
                contributions=contributions,
            )
        except Exception as exc:
            self._metrics.increment("normalization_errors")
            log.error(
                "Normalization failed",
                extra={"event_id": raw.id, "type": raw.type, "error": str(exc)},
                exc_info=exc,
            )
            fallback_normalizer = self._registry.get("__unknown__")
            event = fallback_normalizer.normalize(raw)
            return NormalizationResult(event=event)
