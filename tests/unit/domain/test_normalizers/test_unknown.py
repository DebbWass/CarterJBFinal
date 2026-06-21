from __future__ import annotations

from tests.conftest import make_raw_event
from crater.domain.events.unknown import UnknownEventNormalizer


normalizer = UnknownEventNormalizer()


class TestUnknownEventNormalizer:
    def test_does_not_raise_on_novel_event_type(self):
        raw = make_raw_event(
            event_type="FutureUnknownEvent2077",
            payload={"novel_field": "some_value", "nested": {"more": "stuff"}},
        )
        event = normalizer.normalize(raw)
        assert event.event_type == "FutureUnknownEvent2077"

    def test_raw_payload_preserved(self):
        raw = make_raw_event(
            event_type="QuantumEvent",
            payload={"crater_drift_marker": "injected"},
        )
        event = normalizer.normalize(raw)
        assert event.raw_payload["crater_drift_marker"] == "injected"

    def test_no_commits_extracted(self):
        raw = make_raw_event(event_type="UnknownEvent", payload={"commits": [{"sha": "x"}]})
        assert normalizer.extract_commits(raw) == []

    def test_no_contributions_extracted(self):
        raw = make_raw_event(event_type="UnknownEvent")
        assert normalizer.extract_contributions(raw) == []

    def test_schema_drift_extra_fields_absorbed_by_raw_event(self):
        """extra='allow' on RawEvent means schema-drift fields never crash parse."""
        raw = make_raw_event(
            event_type="WatchEvent",
            payload={"action": "started", "crater_drift_marker": "schema-drift-injected"},
        )
        assert raw.payload["crater_drift_marker"] == "schema-drift-injected"
