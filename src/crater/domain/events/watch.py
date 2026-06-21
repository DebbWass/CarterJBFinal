from __future__ import annotations

from crater.domain.events._helpers import base_event
from crater.domain.events.base import AbstractEventNormalizer
from crater.domain.models import NormalizedEvent, RawEvent


class WatchEventNormalizer(AbstractEventNormalizer):
    """WatchEvent = 'star' event in GH Archive terminology."""

    @property
    def event_type(self) -> str:
        return "WatchEvent"

    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        return base_event(raw)
