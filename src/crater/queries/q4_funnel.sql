-- Q4: Does interest convert to contribution?
-- For repos with >= 500 WatchEvents (stars):
--   - What fraction of stargazers forked within 2 sim-days of starring?
--   - What fraction of forkers opened a PR within 5 sim-days of forking?
-- Time windows are in sim-time (INTERVAL arithmetic against TIMESTAMPTZ columns).

WITH popular_repos AS (
    SELECT repo_id, repo_name, COUNT(*) AS watch_count
    FROM funnel_events
    WHERE event_type = 'WatchEvent'
    GROUP BY repo_id, repo_name
    HAVING COUNT(*) >= 500
),
stars AS (
    SELECT fe.repo_id, fe.actor_login, fe.occurred_at AS starred_at
    FROM funnel_events fe
    JOIN popular_repos pr USING (repo_id)
    WHERE fe.event_type = 'WatchEvent'
),
forks AS (
    SELECT fe.repo_id, fe.actor_login, fe.occurred_at AS forked_at
    FROM funnel_events fe
    JOIN popular_repos pr USING (repo_id)
    WHERE fe.event_type = 'ForkEvent'
),
prs AS (
    SELECT fe.repo_id, fe.actor_login, fe.occurred_at AS pr_at
    FROM funnel_events fe
    JOIN popular_repos pr USING (repo_id)
    WHERE fe.event_type = 'PullRequestEvent'
      AND fe.pr_action  = 'opened'
),
star_fork AS (
    SELECT
        s.repo_id,
        s.actor_login,
        s.starred_at,
        MIN(f.forked_at) AS forked_at
    FROM stars s
    LEFT JOIN forks f
      ON  f.repo_id     = s.repo_id
      AND f.actor_login = s.actor_login
      AND f.forked_at   BETWEEN s.starred_at AND s.starred_at + INTERVAL '2 days'
    GROUP BY s.repo_id, s.actor_login, s.starred_at
),
fork_pr AS (
    SELECT
        sf.repo_id,
        sf.actor_login,
        sf.starred_at,
        sf.forked_at,
        MIN(p.pr_at) AS pr_at
    FROM star_fork sf
    LEFT JOIN prs p
      ON  p.repo_id     = sf.repo_id
      AND p.actor_login = sf.actor_login
      AND sf.forked_at IS NOT NULL
      AND p.pr_at       BETWEEN sf.forked_at AND sf.forked_at + INTERVAL '5 days'
    GROUP BY sf.repo_id, sf.actor_login, sf.starred_at, sf.forked_at
)
SELECT
    pr.repo_name,
    pr.watch_count                                                  AS total_stars,
    COUNT(fp.actor_login)                                           AS total_stargazers,
    SUM(CASE WHEN fp.forked_at IS NOT NULL THEN 1 ELSE 0 END)      AS forked_within_2d,
    ROUND(
        100.0 * SUM(CASE WHEN fp.forked_at IS NOT NULL THEN 1 ELSE 0 END)
            / NULLIF(COUNT(fp.actor_login), 0), 2
    )                                                               AS pct_starred_to_fork,
    SUM(CASE WHEN fp.pr_at IS NOT NULL THEN 1 ELSE 0 END)          AS pr_within_5d_of_fork,
    ROUND(
        100.0 * SUM(CASE WHEN fp.pr_at IS NOT NULL THEN 1 ELSE 0 END)
            / NULLIF(SUM(CASE WHEN fp.forked_at IS NOT NULL THEN 1 ELSE 0 END), 0), 2
    )                                                               AS pct_fork_to_pr
FROM popular_repos pr
JOIN fork_pr fp USING (repo_id)
GROUP BY pr.repo_id, pr.repo_name, pr.watch_count
ORDER BY pr.watch_count DESC;
