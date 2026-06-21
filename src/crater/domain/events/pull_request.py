from __future__ import annotations

from crater.domain.events._helpers import base_event
from crater.domain.events.base import AbstractEventNormalizer
from crater.domain.models import ContributionRecord, NormalizedEvent, RawEvent


class PullRequestEventNormalizer(AbstractEventNormalizer):
    """Normalizes PullRequestEvents.

    Critical invariant: `actor` is whoever closed/merged the PR — NOT the author.
    The PR author lives at payload.pull_request.user.login.
    We use pr_author_login (not actor_login) for all authorship attribution.
    """

    @property
    def event_type(self) -> str:
        return "PullRequestEvent"

    def normalize(self, raw: RawEvent) -> NormalizedEvent:
        event = base_event(raw)
        pr = raw.payload.get("pull_request") or {}
        action = raw.payload.get("action")

        pr_author_login: str | None = None
        user = pr.get("user") or {}
        if isinstance(user, dict):
            pr_author_login = user.get("login") or None

        merged = bool(pr.get("merged", False)) if action == "closed" else None

        base_repo = pr.get("base") or {}
        base_repo_info = base_repo.get("repo") or {}
        language: str | None = base_repo_info.get("language") or None
        base_repo_id: int | None = base_repo_info.get("id") or None

        event.pr_number = pr.get("number")
        event.pr_author_login = pr_author_login
        event.pr_action = action
        event.pr_merged = merged
        event.pr_language = language
        event.pr_base_repo_id = base_repo_id
        return event

    def extract_contributions(self, raw: RawEvent) -> list[ContributionRecord]:
        pr = raw.payload.get("pull_request") or {}
        user = pr.get("user") or {}
        pr_author = user.get("login") if isinstance(user, dict) else None
        if not pr_author:
            return []
        return [
            ContributionRecord(
                actor_login=pr_author,
                repo_id=raw.repo.id,
                repo_name=raw.repo.name,
                contribution_type="pr_author",
                first_contributed=raw.created_at,
            )
        ]
