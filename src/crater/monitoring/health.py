from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from psycopg_pool import AsyncConnectionPool

    from crater.infrastructure.vendor.client import VendorHttpClient

log = logging.getLogger(__name__)


@dataclass
class ComponentHealth:
    name: str
    healthy: bool
    detail: str | None = None


@dataclass
class HealthReport:
    healthy: bool
    components: list[ComponentHealth]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.healthy else "degraded",
            "components": {
                c.name: {"healthy": c.healthy, "detail": c.detail}
                for c in self.components
            },
        }


class HealthProbe:
    """Checks liveness of the vendor, Postgres, and Redis."""

    def __init__(
        self,
        vendor_client: VendorHttpClient,
        pool: AsyncConnectionPool,
        redis_client: aioredis.Redis,
    ) -> None:
        self._vendor = vendor_client
        self._pool = pool
        self._redis = redis_client

    async def check(self) -> HealthReport:
        components = [
            await self._check_vendor(),
            await self._check_postgres(),
            await self._check_redis(),
        ]
        return HealthReport(
            healthy=all(c.healthy for c in components),
            components=components,
        )

    async def _check_vendor(self) -> ComponentHealth:
        try:
            health = await self._vendor.get_health()
            return ComponentHealth(
                name="vendor",
                healthy=True,
                detail=f"simulated_now={health.get('simulated_now')}",
            )
        except Exception as exc:
            return ComponentHealth(name="vendor", healthy=False, detail=str(exc))

    async def _check_postgres(self) -> ComponentHealth:
        try:
            async with self._pool.connection() as conn:
                await conn.execute("SELECT 1")
            return ComponentHealth(name="postgres", healthy=True)
        except Exception as exc:
            return ComponentHealth(name="postgres", healthy=False, detail=str(exc))

    async def _check_redis(self) -> ComponentHealth:
        try:
            await self._redis.ping()
            return ComponentHealth(name="redis", healthy=True)
        except Exception as exc:
            return ComponentHealth(name="redis", healthy=False, detail=str(exc))
