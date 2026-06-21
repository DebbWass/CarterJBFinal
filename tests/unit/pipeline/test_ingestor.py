from __future__ import annotations

import gzip
import json

import pytest

from crater.monitoring.metrics import InMemoryMetricsCollector
from crater.pipeline.ingestor import FileIngestor


def make_gz(lines: list[dict]) -> bytes:
    content = "\n".join(json.dumps(line) for line in lines).encode("utf-8")
    return gzip.compress(content)


def _base_event(
    event_id: str = "e1",
    event_type: str = "WatchEvent",
    actor_login: str = "user",
) -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "created_at": "2024-01-15T00:30:00Z",
        "actor": {"id": 1, "login": actor_login},
        "repo": {"id": 100, "name": "owner/repo"},
        "payload": {},
    }


class TestFileIngestor:
    def setup_method(self):
        self.metrics = InMemoryMetricsCollector()
        self.ingestor = FileIngestor(self.metrics)

    def test_parses_valid_jsonl(self):
        gz = make_gz([_base_event("e1"), _base_event("e2")])
        events = list(self.ingestor.parse(gz))
        assert len(events) == 2
        assert events[0].id == "e1"
        assert events[1].id == "e2"

    def test_skips_malformed_json_lines(self):
        content = b'{"not": "valid json\n' + json.dumps(_base_event("e1")).encode() + b"\n"
        gz = gzip.compress(content)
        events = list(self.ingestor.parse(gz))
        assert len(events) == 1
        assert self.metrics.get_all()["counters"].get("json_parse_errors", 0) >= 1

    def test_skips_empty_lines(self):
        content = b"\n\n" + json.dumps(_base_event("e1")).encode() + b"\n\n"
        gz = gzip.compress(content)
        events = list(self.ingestor.parse(gz))
        assert len(events) == 1

    def test_schema_drift_absorbed(self):
        event = _base_event("e1")
        event["payload"]["crater_drift_marker"] = "injected"
        gz = make_gz([event])
        events = list(self.ingestor.parse(gz))
        assert len(events) == 1
        assert events[0].payload["crater_drift_marker"] == "injected"

    def test_partial_gzip_returns_decompressed_portion(self):
        gz = make_gz([_base_event("e1"), _base_event("e2")])
        truncated = gz[: len(gz) // 2]
        events = list(self.ingestor.parse(truncated))
        assert self.metrics.get_all()["counters"].get("partial_gzip_files", 0) >= 1
