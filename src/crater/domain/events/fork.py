from __future__ import annotations

from crater.domain.events._helpers import base_event
from crater.domain.events.base import AbstractEventNormalizer
from crater.domain.models import NormalizedEvent, RawEvent


class ForkEventNormalizer(AbstractEventNormalizer):
    @property
    def event_type(self) -> str:
        return "ForkEvent"

    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        event = base_event(raw)
        forkee = raw.payload.get("forkee") or {}
        if isinstance(forkee, dict):
            event.fork_forkee_repo_id = forkee.get("id")
        return event
