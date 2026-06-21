-- Q1: What does this person actually code in?
-- For each actor with >= 10 merged PRs, return their top 3 languages by count of merged PRs.
-- PR author = payload.pull_request.user.login (NOT actor — see BRIEF.md note on actor).
-- Language = payload.pull_request.base.repo.language on the merge event.

WITH merged_pr_langs AS (
    SELECT
        pr_author_login                             AS actor,
        pr_language,
        COUNT(*)                                    AS merge_count
    FROM events
    WHERE event_type    = 'PullRequestEvent'
      AND pr_merged     = TRUE
      AND pr_author_login IS NOT NULL
      AND pr_language     IS NOT NULL
      AND NOT is_bot
    GROUP BY pr_author_login, pr_language
),
actor_totals AS (
    SELECT actor, SUM(merge_count) AS total_merges
    FROM merged_pr_langs
    GROUP BY actor
    HAVING SUM(merge_count) >= 10
),
ranked AS (
    SELECT
        m.actor,
        m.pr_language,
        m.merge_count,
        ROW_NUMBER() OVER (
            PARTITION BY m.actor
            ORDER BY m.merge_count DESC, m.pr_language ASC
        ) AS rn
    FROM merged_pr_langs m
    JOIN actor_totals t USING (actor)
)
SELECT
    actor,
    pr_language AS language,
    merge_count
FROM ranked
WHERE rn <= 3
ORDER BY actor, rn;
