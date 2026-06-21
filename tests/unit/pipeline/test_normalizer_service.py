from __future__ import annotations

from tests.conftest import make_raw_event
from crater.domain.events.base import EventNormalizerRegistry
from crater.monitoring.metrics import InMemoryMetricsCollector
from crater.pipeline.normalizer import NormalizationService


class TestNormalizationService:
    def setup_method(self):
        self.metrics = InMemoryMetricsCollector()
        self.service = NormalizationService(
            registry=EventNormalizerRegistry.build_default(),
            metrics=self.metrics,
        )

    def test_known_type_produces_result(self):
        raw = make_raw_event(event_type="WatchEvent")
        result = self.service.process(raw)
        assert result.event.event_type == "WatchEvent"
        assert result.event.event_id == raw.id

    def test_unknown_type_falls_back_gracefully(self):
        raw = make_raw_event(event_type="FutureQuantumEvent")
        result = self.service.process(raw)
        assert result.event.event_type == "FutureQuantumEvent"
        assert self.metrics.get_all()["counters"].get("unknown_event_types", 0) == 1

    def test_push_event_has_commits(self):
        raw = make_raw_event(
            event_type="PushEvent",
            payload={"commits": [{"sha": "abc", "author": {"name": "A", "email": "a@x.com"}}]},
        )
        result = self.service.process(raw)
        assert len(result.commits) == 1

    def test_pr_event_has_contribution(self):
        raw = make_raw_event(
            event_type="PullRequestEvent",
            payload={
                "action": "closed",
                "pull_request": {
                    "merged": True,
                    "user": {"login": "author", "id": 1},
                    "base": {"repo": {"id": 1, "language": "Python"}},
                },
            },
        )
        result = self.service.process(raw)
        assert any(c.actor_login == "author" for c in result.contributions)

    def test_events_normalized_counter_incremented(self):
        raw = make_raw_event(event_type="ForkEvent")
        self.service.process(raw)
        assert self.metrics.get_all()["counters"]["events_normalized"] == 1
