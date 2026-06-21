from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Vendor
    vendor_base_url: str = Field(default="http://gh-archive-vendor:8000")
    fetch_timeout_seconds: float = Field(default=120.0)
    max_fetch_retries: int = Field(default=10)
    outage_backoff_seconds: float = Field(default=5.0)
    poll_interval_seconds: float = Field(default=0.5)

    # Replay window (mirrors vendor env vars)
    replay_window_start: date = Field(default=date(2024, 1, 15))
    replay_window_end: date = Field(default=date(2024, 1, 21))

    # Postgres
    pg_dsn: str = Field(default="postgresql+psycopg://crater:crater@postgres:5432/crater")
    pg_pool_min_size: int = Field(default=2)
    pg_pool_max_size: int = Field(default=10)

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")
    redis_watermark_key: str = Field(default="crater:hwm")

    # Pipeline tuning
    batch_size: int = Field(default=5000)
    flush_interval_seconds: float = Field(default=5.0)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8080)

    # Bot detection: logins containing these strings are flagged is_bot=True
    bot_login_patterns: list[str] = Field(
        default=["[bot]", "-bot", "_bot", "dependabot", "github-actions", "renovate"]
    )
