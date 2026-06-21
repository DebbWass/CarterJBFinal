"""Test the critical invariant: PR author comes from payload, NOT from actor."""
from __future__ import annotations

from tests.conftest import make_raw_event
from crater.domain.events.pull_request import PullRequestEventNormalizer


normalizer = PullRequestEventNormalizer()

_CLOSED_MERGED_PR = {
    "action": "closed",
    "pull_request": {
        "number": 42,
        "merged": True,
        "user": {"login": "pr-author-login", "id": 999},
        "base": {
            "repo": {
                "id": 555,
                "language": "Python",
            }
        },
    },
}

_OPENED_PR = {
    "action": "opened",
    "pull_request": {
        "number": 7,
        "merged": False,
        "user": {"login": "opener-login", "id": 888},
        "base": {"repo": {"id": 555, "language": "Go"}},
    },
}


class TestPullRequestEventNormalizer:
    def test_pr_author_is_payload_user_not_actor(self):
        raw = make_raw_event(
            event_type="PullRequestEvent",
            actor_login="merger-login",
            payload=_CLOSED_MERGED_PR,
        )
        event = normalizer.normalize(raw)
        assert event.pr_author_login == "pr-author-login"
        assert event.actor_login == "merger-login"

    def test_merged_flag_true_for_closed_merged(self):
        raw = make_raw_event(event_type="PullRequestEvent", payload=_CLOSED_MERGED_PR)
        event = normalizer.normalize(raw)
        assert event.pr_merged is True

    def test_merged_flag_none_for_opened(self):
        raw = make_raw_event(event_type="PullRequestEvent", payload=_OPENED_PR)
        event = normalizer.normalize(raw)
        assert event.pr_merged is None

    def test_language_extracted(self):
        raw = make_raw_event(event_type="PullRequestEvent", payload=_CLOSED_MERGED_PR)
        event = normalizer.normalize(raw)
        assert event.pr_language == "Python"

    def test_contribution_uses_pr_author_not_actor(self):
        raw = make_raw_event(
            event_type="PullRequestEvent",
            actor_login="merger-login",
            payload=_CLOSED_MERGED_PR,
        )
        contribs = normalizer.extract_contributions(raw)
        assert len(contribs) == 1
        assert contribs[0].actor_login == "pr-author-login"
        assert contribs[0].contribution_type == "pr_author"

    def test_no_contribution_when_pr_user_missing(self):
        raw = make_raw_event(
            event_type="PullRequestEvent",
            payload={"action": "labeled", "pull_request": {}},
        )
        contribs = normalizer.extract_contributions(raw)
        assert contribs == []
