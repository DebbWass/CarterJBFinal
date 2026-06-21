from __future__ import annotations

from tests.conftest import make_raw_event
from crater.domain.events.push import PushEventNormalizer


normalizer = PushEventNormalizer()

_NORMAL_PUSH = {
    "ref": "refs/heads/main",
    "forced": False,
    "commits": [
        {"sha": "abc123", "author": {"name": "Alice Smith", "email": "alice@example.com"}},
        {"sha": "def456", "author": {"name": "Bob Jones", "email": "bob@example.com"}},
    ],
}

_FORCED_PUSH = {
    "ref": "refs/heads/main",
    "forced": True,
    "commits": [
        {"sha": "ghi789", "author": {"name": "Alice Smith", "email": "alice@example.com"}},
    ],
}


class TestPushEventNormalizer:
    def test_extracts_two_commits(self):
        raw = make_raw_event(event_type="PushEvent", actor_login="pusher", payload=_NORMAL_PUSH)
        commits = normalizer.extract_commits(raw)
        assert len(commits) == 2
        assert commits[0].author_name == "Alice Smith"
        assert commits[0].author_email == "alice@example.com"

    def test_commit_sha_captured(self):
        raw = make_raw_event(event_type="PushEvent", payload=_NORMAL_PUSH)
        commits = normalizer.extract_commits(raw)
        assert commits[0].sha == "abc123"

    def test_forced_flag_false_for_normal_push(self):
        raw = make_raw_event(event_type="PushEvent", payload=_NORMAL_PUSH)
        commits = normalizer.extract_commits(raw)
        assert all(c.forced is False for c in commits)

    def test_forced_flag_true_for_forced_push(self):
        raw = make_raw_event(event_type="PushEvent", payload=_FORCED_PUSH)
        commits = normalizer.extract_commits(raw)
        assert all(c.forced is True for c in commits)

    def test_contribution_type_is_commit_author(self):
        raw = make_raw_event(event_type="PushEvent", actor_login="pusher", payload=_NORMAL_PUSH)
        contribs = normalizer.extract_contributions(raw)
        assert len(contribs) == 1
        assert contribs[0].actor_login == "pusher"
        assert contribs[0].contribution_type == "commit_author"

    def test_empty_commits_list(self):
        raw = make_raw_event(event_type="PushEvent", payload={"commits": []})
        commits = normalizer.extract_commits(raw)
        assert commits == []
