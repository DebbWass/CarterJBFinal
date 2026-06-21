from __future__ import annotations

from tests.conftest import make_raw_event
from crater.domain.events.fork import ForkEventNormalizer


normalizer = ForkEventNormalizer()


class TestForkEventNormalizer:
    def test_extracts_forkee_repo_id(self):
        raw = make_raw_event(
            event_type="ForkEvent",
            payload={"forkee": {"id": 9999, "name": "octocat/repo-fork", "full_name": "octocat/repo-fork"}},
        )
        event = normalizer.normalize(raw)
        assert event.fork_forkee_repo_id == 9999

    def test_forkee_missing_payload(self):
        raw = make_raw_event(event_type="ForkEvent", payload={})
        event = normalizer.normalize(raw)
        assert event.fork_forkee_repo_id is None
