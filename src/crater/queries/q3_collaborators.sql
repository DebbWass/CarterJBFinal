-- Q3: Who works well with whom?
-- Top 10 pairs of developers who contributed to >= 3 distinct repos together.
-- "Contributed" = appearing as PR author or commit author on that repo.
-- Pair is unordered; ranked by shared repos DESC, then combined contributions DESC.

WITH pairs AS (
    SELECT
        LEAST(a.actor_login, b.actor_login)    AS actor_a,
        GREATEST(a.actor_login, b.actor_login) AS actor_b,
        a.repo_id,
        a.repo_name
    FROM actor_repo_contributions a
    JOIN actor_repo_contributions b
      ON  a.repo_id      = b.repo_id
      AND a.actor_login  < b.actor_login
),
pair_stats AS (
    SELECT
        actor_a,
        actor_b,
        COUNT(DISTINCT repo_id)  AS shared_repos,
        COUNT(*)                 AS combined_contributions
    FROM pairs
    GROUP BY actor_a, actor_b
    HAVING COUNT(DISTINCT repo_id) >= 3
)
SELECT
    actor_a,
    actor_b,
    shared_repos,
    combined_contributions
FROM pair_stats
ORDER BY shared_repos DESC, combined_contributions DESC
LIMIT 10;
