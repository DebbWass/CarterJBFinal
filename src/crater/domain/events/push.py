from __future__ import annotations

from crater.domain.events._helpers import base_event
from crater.domain.events.base import AbstractEventNormalizer
from crater.domain.models import (
    ContributionRecord,
    NormalizedEvent,
    PushCommitRecord,
    RawEvent,
)


class PushEventNormalizer(AbstractEventNormalizer):
    @property
    def event_type(self) -> str:
        return "PushEvent"

    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        return base_event(raw)

    def extract_commits(self, raw: RawEvent) -> list[PushCommitRecord]:
        forced: bool = bool(raw.payload.get("forced", False))
        commits: list[dict] = raw.payload.get("commits", []) or []
        records: list[PushCommitRecord] = []
        for commit in commits:
            if not isinstance(commit, dict):
                continue
            author = commit.get("author") or {}
            records.append(
                PushCommitRecord(
                    event_id=raw.id,
                    repo_id=raw.repo.id,
                    repo_name=raw.repo.name,
                    pusher_login=raw.actor.login,
                    pushed_at=raw.created_at,
                    author_name=author.get("name"),
                    author_email=author.get("email"),
                    sha=commit.get("sha"),
                    forced=forced,
                )
            )
        return records

    def extract_contributions(self, raw: RawEvent) -> list[ContributionRecord]:
        if not raw.actor.login:
            return []
        return [
            ContributionRecord(
                actor_login=raw.actor.login,
                repo_id=raw.repo.id,
                repo_name=raw.repo.name,
                contribution_type="commit_author",
                first_contributed=raw.created_at,
            )
        ]
