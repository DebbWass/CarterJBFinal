"""Shared test fixtures."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from crater.domain.events.base import EventNormalizerRegistry
from crater.domain.models import RawEvent
from crater.infrastructure.redis.watermark_store import InMemoryWatermarkStore
from crater.monitoring.metrics import InMemoryMetricsCollector


def make_raw_event(
    event_id: str = "test-1",
    event_type: str = "WatchEvent",
    actor_login: str = "octocat",
    actor_id: int = 1,
    repo_id: int = 100,
    repo_name: str = "owner/repo",
    created_at: str = "2024-01-15T00:30:00Z",
    payload: dict[str, Any] | None = None,
) -> RawEvent:
    return RawEvent.model_validate(
        {
            "id": event_id,
            "type": event_type,
            "created_at": created_at,
            "actor": {"id": actor_id, "login": actor_login},
            "repo": {"id": repo_id, "name": repo_name},
            "payload": payload or {},
        }
    )


@pytest.fixture
def raw_event_factory():
    return make_raw_event


@pytest.fixture
def metrics():
    return InMemoryMetricsCollector()


@pytest.fixture
def watermark_store():
    return InMemoryWatermarkStore()


@pytest.fixture
def registry():
    return EventNormalizerRegistry.build_default()


@pytest.fixture
def utc_dt():
    def _make(iso: str) -> datetime:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
    return _make
