from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from crater.config.settings import PipelineSettings
from crater.pipeline.errors import TruncatedResponseError

log = logging.getLogger(__name__)


class VendorHttpClient:
    """HTTP transport against the gh-archive-vendor API.

    Responsibilities:
    - Execute GET requests for hourly files and operational endpoints.
    - Detect Content-Length mismatches (truncated responses) and raise
      TruncatedResponseError.
    - Retry transient network errors with exponential backoff.
    - Return plain (status_code, bytes | None) — no watermark or filename logic.

    Does NOT handle 404/503 retry policy — that is FileFetcher's job.
    """

    def __init__(self, settings: PipelineSettings) -> None:
        self._base_url = settings.vendor_base_url.rstrip("/")
        self._timeout = settings.fetch_timeout_seconds
        self._max_retries = settings.max_fetch_retries
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(connect=10.0, read=self._timeout, write=10.0, pool=10.0),
            follow_redirects=True,
        )

    async def get_health(self) -> dict[str, Any]:
        resp = await self._client.get("/healthz")
        resp.raise_for_status()
        return resp.json()

    async def get_simulated_now(self) -> datetime:
        resp = await self._client.get("/simulated_now")
        resp.raise_for_status()
        raw = resp.json()["simulated_now"]
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc)

    async def fetch_file(self, filename: str) -> tuple[int, bytes | None]:
        """Fetch a single hourly file.

        Returns:
            (200, bytes)   — success; bytes is the full gzip body
            (404, None)    — sim clock not reached yet (or late-file chaos)
            (503, None)    — vendor outage window

        Raises:
            TruncatedResponseError — Content-Length declared but body is shorter
            httpx.HTTPError        — network-level failures after all retries
        """
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._client.get(f"/{filename}")

                if resp.status_code in (404, 503):
                    return resp.status_code, None

                resp.raise_for_status()

                body = resp.content
                declared = resp.headers.get("content-length")
                if declared is not None and len(body) < int(declared):
                    raise TruncatedResponseError(filename, int(declared), len(body))

                return 200, body

            except TruncatedResponseError:
                raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                if attempt == self._max_retries:
                    log.error(
                        "Vendor request failed after retries",
                        extra={"gh_filename": filename, "attempts": attempt, "error": str(exc)},
                    )
                    raise
                backoff = min(2**attempt, 30)
                log.warning(
                    "Vendor request failed, retrying",
                    extra={"gh_filename": filename, "attempt": attempt, "backoff": backoff},
                )
                time.sleep(backoff)

        return 503, None

    async def aclose(self) -> None:
        await self._client.aclose()
