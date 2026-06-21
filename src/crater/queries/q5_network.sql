-- Q5: Who's in this person's network?
-- Given a seed actor (:seed_actor), return every actor at collaboration distance
-- 1 or 2, along with the distance and the repos that connect them.
--
-- Distance 1 = actor shares at least one repo with the seed.
-- Distance 2 = actor shares a repo with a distance-1 actor (but NOT with the seed directly).
--
-- Run with: psql -v seed_actor="'torvalds'" -f q5_network.sql
-- or:       psql -c "SET app.seed_actor = 'torvalds'" -f q5_network.sql

-- Distance-1: all actors who share at least one repo with the seed
WITH dist1 AS (
    SELECT DISTINCT
        b.actor_login  AS neighbor,
        a.repo_id,
        a.repo_name,
        1              AS distance
    FROM actor_repo_contributions a
    JOIN actor_repo_contributions b
      ON  a.repo_id      = b.repo_id
      AND b.actor_login <> :seed_actor
    WHERE a.actor_login = :seed_actor
),
-- Distance-2: actors who share a repo with any dist-1 actor,
-- excluding the seed and any actor already at distance 1
dist2 AS (
    SELECT DISTINCT
        b.actor_login  AS neighbor,
        a.repo_id,
        a.repo_name,
        2              AS distance
    FROM actor_repo_contributions a
    JOIN actor_repo_contributions b
      ON  a.repo_id      = b.repo_id
      AND b.actor_login <> :seed_actor
    WHERE a.actor_login IN (SELECT neighbor FROM dist1)
      AND b.actor_login NOT IN (SELECT neighbor FROM dist1)
      AND b.actor_login <> :seed_actor
),
all_distances AS (
    SELECT neighbor, repo_id, repo_name, distance FROM dist1
    UNION ALL
    SELECT neighbor, repo_id, repo_name, distance FROM dist2
)
SELECT
    neighbor                                             AS actor,
    MIN(distance)                                        AS distance,
    ARRAY_AGG(DISTINCT repo_name ORDER BY repo_name)    AS connecting_repos
FROM all_distances
GROUP BY neighbor
ORDER BY distance ASC, neighbor ASC;
