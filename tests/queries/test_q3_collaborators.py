"""Q3 contract test: top developer pairs sharing >= 3 repos."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_q3_alice_bob_share_three_repos(pool):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                WITH pairs AS (
                    SELECT
                        LEAST(a.actor_login, b.actor_login)    AS actor_a,
                        GREATEST(a.actor_login, b.actor_login) AS actor_b,
                        a.repo_id
                    FROM actor_repo_contributions a
                    JOIN actor_repo_contributions b
                      ON a.repo_id = b.repo_id AND a.actor_login < b.actor_login
                ),
                pair_stats AS (
                    SELECT actor_a, actor_b, COUNT(DISTINCT repo_id) AS shared_repos
                    FROM pairs
                    GROUP BY actor_a, actor_b
                    HAVING COUNT(DISTINCT repo_id) >= 3
                )
                SELECT actor_a, actor_b, shared_repos
                FROM pair_stats
                ORDER BY shared_repos DESC
                LIMIT 10
            """)
            rows = await cur.fetchall()

    pair = next(
        (r for r in rows if set([r[0], r[1]]) == {"alice", "bob"}),
        None,
    )
    assert pair is not None, "alice-bob should appear in Q3 results (3 shared repos)"
    assert pair[2] == 3


@pytest.mark.asyncio
async def test_q3_carol_alice_do_not_meet_threshold(pool):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                WITH pairs AS (
                    SELECT
                        LEAST(a.actor_login, b.actor_login)    AS actor_a,
                        GREATEST(a.actor_login, b.actor_login) AS actor_b,
                        a.repo_id
                    FROM actor_repo_contributions a
                    JOIN actor_repo_contributions b
                      ON a.repo_id = b.repo_id AND a.actor_login < b.actor_login
                ),
                pair_stats AS (
                    SELECT actor_a, actor_b, COUNT(DISTINCT repo_id) AS shared_repos
                    FROM pairs
                    GROUP BY actor_a, actor_b
                    HAVING COUNT(DISTINCT repo_id) >= 3
                )
                SELECT actor_a, actor_b FROM pair_stats
            """)
            rows = await cur.fetchall()

    carol_alice = next(
        (r for r in rows if set([r[0], r[1]]) == {"alice", "carol"}),
        None,
    )
    assert carol_alice is None, "carol-alice share only 2 repos and should not appear"
