from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pydantic import ValidationError

from crater.domain.models import RawEvent

if TYPE_CHECKING:
    from crater.monitoring.metrics import MetricsCollector

log = logging.getLogger(__name__)


class FileIngestor:
    """Decompresses gzip bytes and yields parsed RawEvent objects.

    Design invariants:
    - Malformed JSON lines are logged and skipped; processing continues.
    - Partial gzip streams (truncated files) are handled: whatever bytes
      successfully decompressed are processed; the rest are discarded.
    - Pydantic validation failures (structurally invalid events) are logged
      and skipped — we never drop an entire file for one bad line.
    - Schema drift (extra fields in payload) is absorbed by RawEvent's
      extra="allow" config; these normalizers will carry the extra data
      through to raw_payload in Postgres.
    """

    def __init__(self, metrics: MetricsCollector) -> None:
        self._metrics = metrics

    def parse(self, gz_bytes: bytes) -> Iterator[RawEvent]:
        raw_text = self._decompress_safe(gz_bytes)
        lines = raw_text.split(b"\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            event = self._parse_line(line)
            if event is not None:
                yield event

    def _decompress_safe(self, gz_bytes: bytes) -> bytes:
        """Decompress gzip bytes, tolerating truncated streams.

        If the stream is complete, returns the full decompressed content.
        If truncated (EOFError / BadGzipFile), returns whatever bytes were
        successfully decompressed up to the cut point — these are valid events.
        """
        try:
            return gzip.decompress(gz_bytes)
        except (EOFError, gzip.BadGzipFile, OSError):
            log.warning("Partial gzip detected — processing available bytes")
            self._metrics.increment("partial_gzip_files")
            return self._decompress_partial(gz_bytes)

    @staticmethod
    def _decompress_partial(gz_bytes: bytes) -> bytes:
        """Best-effort decompression of a truncated gzip stream."""
        import zlib
        try:
            d = zlib.decompressobj(wbits=47)
            return d.decompress(gz_bytes)
        except zlib.error:
            return b""

    def _parse_line(self, line: bytes) -> RawEvent | None:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            self._metrics.increment("json_parse_errors")
            log.debug("JSON parse error", extra={"error": str(exc)})
            return None

        try:
            return RawEvent.model_validate(data)
        except ValidationError as exc:
            self._metrics.increment("validation_errors")
            log.debug("Event validation error", extra={"error": str(exc)})
            return None
