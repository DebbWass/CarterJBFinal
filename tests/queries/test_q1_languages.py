"""Q1 contract test: top 3 languages per actor with >= 10 merged PRs."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_q1_alice_top_language_is_python(pool):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                WITH merged_pr_langs AS (
                    SELECT pr_author_login AS actor, pr_language, COUNT(*) AS merge_count
                    FROM events
                    WHERE event_type = 'PullRequestEvent'
                      AND pr_merged = TRUE
                      AND pr_author_login IS NOT NULL
                      AND pr_language IS NOT NULL
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
                    SELECT m.actor, m.pr_language, m.merge_count,
                           ROW_NUMBER() OVER (PARTITION BY m.actor ORDER BY m.merge_count DESC) AS rn
                    FROM merged_pr_langs m
                    JOIN actor_totals t USING (actor)
                )
                SELECT actor, pr_language, merge_count
                FROM ranked WHERE rn = 1
            """)
            rows = await cur.fetchall()

    assert len(rows) >= 1
    alice_row = next((r for r in rows if r[0] == "alice"), None)
    assert alice_row is not None, "alice should appear in Q1 results"
    assert alice_row[1] == "Python", "alice's top language should be Python"
    assert alice_row[2] == 10


@pytest.mark.asyncio
async def test_q1_returns_at_most_3_per_actor(pool):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                WITH merged_pr_langs AS (
                    SELECT pr_author_login AS actor, pr_language, COUNT(*) AS merge_count
                    FROM events
                    WHERE event_type='PullRequestEvent' AND pr_merged=TRUE
                      AND pr_author_login IS NOT NULL AND pr_language IS NOT NULL AND NOT is_bot
                    GROUP BY pr_author_login, pr_language
                ),
                actor_totals AS (
                    SELECT actor FROM merged_pr_langs GROUP BY actor HAVING SUM(merge_count) >= 10
                ),
                ranked AS (
                    SELECT m.actor, m.pr_language, m.merge_count,
                           ROW_NUMBER() OVER (PARTITION BY m.actor ORDER BY m.merge_count DESC) AS rn
                    FROM merged_pr_langs m JOIN actor_totals t USING (actor)
                )
                SELECT actor, COUNT(*) AS lang_count
                FROM ranked WHERE rn <= 3
                GROUP BY actor
            """)
            rows = await cur.fetchall()
    for actor, lang_count in rows:
        assert lang_count <= 3, f"{actor} has more than 3 languages in Q1 result"
