from __future__ import annotations

import redis.asyncio as aioredis

from crater.config.settings import PipelineSettings


def create_redis_client(settings: PipelineSettings) -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
