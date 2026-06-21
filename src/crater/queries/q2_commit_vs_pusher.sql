-- Q2: Who actually writes the code in this repo?
-- Top 50 repos by PR activity: top 5 commit authors vs top 5 pushers, side by side.
-- Commit author = push_commits.author_name/email (excludes forced=TRUE commits per BRIEF.md).
-- Pusher = push_commits.pusher_login (the actor on the PushEvent).

WITH top_repos AS (
    SELECT repo_id, repo_name, COUNT(*) AS pr_count
    FROM events
    WHERE event_type = 'PullRequestEvent'
    GROUP BY repo_id, repo_name
    ORDER BY pr_count DESC
    LIMIT 50
),
commit_authors AS (
    SELECT
        pc.repo_id,
        pc.author_name,
        pc.author_email,
        COUNT(*)    AS commit_count,
        ROW_NUMBER() OVER (
            PARTITION BY pc.repo_id
            ORDER BY COUNT(*) DESC, pc.author_name ASC
        ) AS rn
    FROM push_commits pc
    JOIN top_repos tr USING (repo_id)
    WHERE pc.author_name IS NOT NULL
      AND pc.forced = FALSE
    GROUP BY pc.repo_id, pc.author_name, pc.author_email
),
pushers AS (
    SELECT
        pc.repo_id,
        pc.pusher_login,
        COUNT(DISTINCT pc.event_id) AS push_count,
        ROW_NUMBER() OVER (
            PARTITION BY pc.repo_id
            ORDER BY COUNT(DISTINCT pc.event_id) DESC, pc.pusher_login ASC
        ) AS rn
    FROM push_commits pc
    JOIN top_repos tr USING (repo_id)
    GROUP BY pc.repo_id, pc.pusher_login
)
SELECT
    tr.repo_name,
    tr.pr_count,
    ca.author_name,
    ca.author_email,
    ca.commit_count,
    ca.rn      AS commit_author_rank,
    p.pusher_login,
    p.push_count,
    p.rn       AS pusher_rank
FROM top_repos tr
LEFT JOIN commit_authors ca ON ca.repo_id = tr.repo_id AND ca.rn <= 5
LEFT JOIN pushers          p ON p.repo_id  = tr.repo_id AND p.rn  <= 5
ORDER BY tr.pr_count DESC, tr.repo_name, ca.rn NULLS LAST, p.rn NULLS LAST;
