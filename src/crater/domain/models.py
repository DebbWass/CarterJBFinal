from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActorModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | None = None
    login: str = ""
    display_login: str | None = None
    gravatar_id: str | None = None
    url: str | None = None
    avatar_url: str | None = None


class RepoModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    url: str | None = None


class RawEvent(BaseModel):
    """One JSONL line from the vendor. extra='allow' absorbs schema drift silently."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    created_at: datetime
    actor: ActorModel = Field(default_factory=ActorModel)
    repo: RepoModel
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class NormalizedEvent:
    """Flattened, storage-ready representation of one GitHub event."""

    event_id: str
    event_type: str
    created_at: datetime
    actor_login: str
    actor_id: int | None
    is_bot: bool
    repo_id: int
    repo_name: str

    # PullRequestEvent fields (None for other types)
    pr_number: int | None = None
    pr_author_login: str | None = None
    pr_action: str | None = None
    pr_merged: bool | None = None
    pr_language: str | None = None
    pr_base_repo_id: int | None = None

    # ForkEvent fields
    fork_forkee_repo_id: int | None = None

    # Full payload stored as JSONB for unknown types and future queries
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class PushCommitRecord:
    """One row in push_commits — a single commit extracted from a PushEvent."""

    event_id: str
    repo_id: int
    repo_name: str
    pusher_login: str
    pushed_at: datetime
    author_name: str | None = None
    author_email: str | None = None
    sha: str | None = None
    forced: bool = False


@dataclass
class ContributionRecord:
    """One (actor, repo, type) de-duplicated contribution row for Q3/Q5."""

    actor_login: str
    repo_id: int
    repo_name: str
    contribution_type: str  # 'pr_author' | 'commit_author'
    first_contributed: datetime


@dataclass
class NormalizationResult:
    """The full output of normalizing one RawEvent."""

    event: NormalizedEvent
    commits: list[PushCommitRecord] = field(default_factory=list)
    contributions: list[ContributionRecord] = field(default_factory=list)
