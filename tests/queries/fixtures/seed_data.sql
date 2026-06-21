-- Minimal deterministic seed data for Q1–Q5 analyst query tests.
-- Designed to produce known, assertable results.

TRUNCATE events, push_commits, actor_repo_contributions, funnel_events RESTART IDENTITY CASCADE;

-- ─── Events ─────────────────────────────────────────────────────────────────
-- 10 merged PRs for 'alice' in Python (satisfies Q1 >= 10 threshold)
INSERT INTO events (event_id, event_type, created_at, actor_login, actor_id, is_bot, repo_id, repo_name, pr_author_login, pr_action, pr_merged, pr_language)
SELECT
    'pr-alice-py-' || n,
    'PullRequestEvent',
    '2024-01-15T00:00:00Z'::timestamptz + (n || ' hours')::interval,
    'merger',
    2,
    FALSE,
    1000,
    'owner/python-repo',
    'alice',
    'closed',
    TRUE,
    'Python'
FROM generate_series(1, 10) AS n;

-- 5 merged PRs for 'alice' in Go (below top-3 threshold individually but present)
INSERT INTO events (event_id, event_type, created_at, actor_login, actor_id, is_bot, repo_id, repo_name, pr_author_login, pr_action, pr_merged, pr_language)
SELECT
    'pr-alice-go-' || n,
    'PullRequestEvent',
    '2024-01-16T00:00:00Z'::timestamptz + (n || ' hours')::interval,
    'merger',
    2,
    FALSE,
    1001,
    'owner/go-repo',
    'alice',
    'closed',
    TRUE,
    'Go'
FROM generate_series(1, 5) AS n;

-- ─── Push commits for Q2 ─────────────────────────────────────────────────────
INSERT INTO events (event_id, event_type, created_at, actor_login, actor_id, is_bot, repo_id, repo_name)
VALUES ('push-1', 'PushEvent', '2024-01-15T01:00:00Z', 'bob', 3, FALSE, 1000, 'owner/python-repo');

INSERT INTO push_commits (event_id, repo_id, repo_name, pusher_login, author_name, author_email, sha, forced, pushed_at)
VALUES
    ('push-1', 1000, 'owner/python-repo', 'bob', 'Alice Smith', 'alice@example.com', 'abc123', FALSE, '2024-01-15T01:00:00Z'),
    ('push-1', 1000, 'owner/python-repo', 'bob', 'Charlie Dev', 'charlie@example.com', 'def456', FALSE, '2024-01-15T01:00:00Z');

-- ─── Contributions for Q3/Q5 ─────────────────────────────────────────────────
INSERT INTO actor_repo_contributions (actor_login, repo_id, repo_name, contribution_type, first_contributed)
VALUES
    ('alice', 1000, 'owner/python-repo', 'pr_author', '2024-01-15T00:01:00Z'),
    ('alice', 1001, 'owner/go-repo', 'pr_author', '2024-01-16T00:01:00Z'),
    ('alice', 1002, 'owner/rust-repo', 'commit_author', '2024-01-17T00:01:00Z'),
    ('bob',   1000, 'owner/python-repo', 'commit_author', '2024-01-15T01:00:00Z'),
    ('bob',   1001, 'owner/go-repo', 'pr_author', '2024-01-16T02:00:00Z'),
    ('bob',   1002, 'owner/rust-repo', 'commit_author', '2024-01-17T02:00:00Z'),
    ('carol', 1000, 'owner/python-repo', 'pr_author', '2024-01-15T03:00:00Z'),
    ('carol', 1001, 'owner/go-repo', 'commit_author', '2024-01-16T03:00:00Z');

-- ─── Funnel events for Q4 ────────────────────────────────────────────────────
-- Popular repo with 600 stars
INSERT INTO funnel_events (actor_login, repo_id, repo_name, event_type, occurred_at)
SELECT 'user' || n, 2000, 'popular/repo', 'WatchEvent', '2024-01-15T00:00:00Z'::timestamptz + (n || ' minutes')::interval
FROM generate_series(1, 600) AS n;

-- 60 of those users forked within 2 sim-days
INSERT INTO funnel_events (actor_login, repo_id, repo_name, event_type, occurred_at)
SELECT 'user' || n, 2000, 'popular/repo', 'ForkEvent', '2024-01-15T12:00:00Z'::timestamptz + (n || ' minutes')::interval
FROM generate_series(1, 60) AS n;

-- 10 of the forkers opened a PR within 5 sim-days
INSERT INTO funnel_events (actor_login, repo_id, repo_name, event_type, occurred_at, pr_action)
SELECT 'user' || n, 2000, 'popular/repo', 'PullRequestEvent', '2024-01-17T00:00:00Z'::timestamptz + (n || ' minutes')::interval, 'opened'
FROM generate_series(1, 10) AS n;
