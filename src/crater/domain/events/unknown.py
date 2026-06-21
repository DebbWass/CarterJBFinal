from __future__ import annotations

from crater.domain.events._helpers import base_event
from crater.domain.events.base import AbstractEventNormalizer
from crater.domain.models import NormalizedEvent, RawEvent


class UnknownEventNormalizer(AbstractEventNormalizer):
    """Fallback normalizer for any event type not explicitly handled.

    Stores the full raw_payload as JSONB so future analysts can query novel
    event types without re-fetching history. Never raises; never drops an event.
    """

    @property
    def event_type(self) -> str:
        return "__unknown__"

    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        return base_event(raw)
