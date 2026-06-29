"""DDL for all Crater tables and indexes.

All statements use IF NOT EXISTS so they are safe to run at every startup
(idempotent). New columns must be added with ALTER TABLE ... ADD COLUMN IF NOT EXISTS
in a future migration block, not by modifying existing CREATE TABLE statements.
"""

EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    event_id            TEXT        NOT NULL,
    event_type          TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL,
    actor_login         TEXT        NOT NULL,
    actor_id            BIGINT,
    is_bot              BOOLEAN     NOT NULL DEFAULT FALSE,
    repo_id             BIGINT      NOT NULL,
    repo_name           TEXT        NOT NULL,
    pr_number           INTEGER,
    pr_author_login     TEXT,
    pr_action           TEXT,
    pr_merged           BOOLEAN,
    pr_language         TEXT,
    pr_base_repo_id     BIGINT,
    fork_forkee_repo_id BIGINT,
    raw_payload         JSONB       NOT NULL DEFAULT '{}',
    CONSTRAINT events_pkey PRIMARY KEY (event_id)
);
"""

PUSH_COMMITS_TABLE = """
CREATE TABLE IF NOT EXISTS push_commits (
    id              BIGSERIAL   PRIMARY KEY,
    event_id        TEXT        NOT NULL REFERENCES events(event_id),
    repo_id         BIGINT      NOT NULL,
    repo_name       TEXT        NOT NULL,
    pusher_login    TEXT        NOT NULL,
    author_name     TEXT,
    author_email    TEXT,
    sha             TEXT,
    forced          BOOLEAN     NOT NULL DEFAULT FALSE,
    pushed_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT pc_event_sha_uniq UNIQUE (event_id, sha)
);
"""

CONTRIBUTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS actor_repo_contributions (
    actor_login         TEXT        NOT NULL,
    repo_id             BIGINT      NOT NULL,
    repo_name           TEXT        NOT NULL,
    contribution_type   TEXT        NOT NULL,
    first_contributed   TIMESTAMPTZ NOT NULL,
    CONSTRAINT arc_pkey PRIMARY KEY (actor_login, repo_id, contribution_type)
);
"""

FUNNEL_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS funnel_events (
    actor_login TEXT        NOT NULL,
    repo_id     BIGINT      NOT NULL,
    repo_name   TEXT        NOT NULL,
    event_type  TEXT        NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    pr_action   TEXT,
    CONSTRAINT funnel_events_pkey PRIMARY KEY (actor_login, repo_id, event_type, occurred_at)
);
"""

PIPELINE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_files (
    filename    TEXT        NOT NULL PRIMARY KEY,
    sim_hour    TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_count INTEGER     NOT NULL DEFAULT 0,
    status      TEXT        NOT NULL DEFAULT 'done'
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS events_type_idx       ON events (event_type);",
    "CREATE INDEX IF NOT EXISTS events_actor_idx      ON events (actor_login);",
    "CREATE INDEX IF NOT EXISTS events_repo_idx       ON events (repo_id);",
    "CREATE INDEX IF NOT EXISTS events_created_idx    ON events (created_at);",
    "CREATE INDEX IF NOT EXISTS events_pr_author_idx  ON events (pr_author_login) WHERE pr_author_login IS NOT NULL;",
    "CREATE INDEX IF NOT EXISTS events_pr_merged_idx  ON events (pr_merged, pr_language) WHERE pr_merged = TRUE;",
    "CREATE INDEX IF NOT EXISTS pc_repo_idx           ON push_commits (repo_id);",
    "CREATE INDEX IF NOT EXISTS pc_author_idx         ON push_commits (author_name, author_email);",
    "CREATE INDEX IF NOT EXISTS pc_pusher_idx         ON push_commits (pusher_login);",
    "CREATE INDEX IF NOT EXISTS arc_actor_idx         ON actor_repo_contributions (actor_login);",
    "CREATE INDEX IF NOT EXISTS arc_repo_idx          ON actor_repo_contributions (repo_id);",
    "CREATE INDEX IF NOT EXISTS fe_repo_type_idx      ON funnel_events (repo_id, event_type);",
    "CREATE INDEX IF NOT EXISTS fe_actor_idx          ON funnel_events (actor_login);",
    "CREATE INDEX IF NOT EXISTS fe_occurred_idx       ON funnel_events (occurred_at);",
]

ALL_DDL: list[str] = [
    EVENTS_TABLE,
    PUSH_COMMITS_TABLE,
    CONTRIBUTIONS_TABLE,
    FUNNEL_EVENTS_TABLE,
    PIPELINE_FILES_TABLE,
    *INDEXES,
]
