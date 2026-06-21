"""Shared helpers for event normalizers."""
from __future__ import annotations

from crater.domain.models import NormalizedEvent, RawEvent

_BOT_PATTERNS = ("[bot]", "-bot", "_bot", "dependabot", "github-actions", "renovate")


def is_bot_login(login: str) -> bool:
    lower = login.lower()
    return any(p in lower for p in _BOT_PATTERNS)


def base_event(raw: RawEvent) -> NormalizedEvent:
    """Build a NormalizedEvent with fields common to every event type."""
    return NormalizedEvent(
        event_id=raw.id,
        event_type=raw.type,
        created_at=raw.created_at,
        actor_login=raw.actor.login,
        actor_id=raw.actor.id,
        is_bot=is_bot_login(raw.actor.login),
        repo_id=raw.repo.id,
        repo_name=raw.repo.name,
        raw_payload=raw.payload,
    )
