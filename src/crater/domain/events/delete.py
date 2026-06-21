from __future__ import annotations

from crater.domain.events._helpers import base_event
from crater.domain.events.base import AbstractEventNormalizer
from crater.domain.models import NormalizedEvent, RawEvent


class DeleteEventNormalizer(AbstractEventNormalizer):
    @property
    def event_type(self) -> str:
        return "DeleteEvent"

    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        return base_event(raw)
