from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any


class MetricsCollector(ABC):
    @abstractmethod
    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter by value."""

    @abstractmethod
    def gauge(self, name: str, value: float) -> None:
        """Set a gauge to value."""

    @abstractmethod
    def get_all(self) -> dict[str, Any]:
        """Return a snapshot of all current metrics."""


class InMemoryMetricsCollector(MetricsCollector):
    """Thread-safe in-process counter and gauge store.

    Exposed via the /status API endpoint. No external dependency required.
    Replace with a Prometheus exporter by implementing the ABC and injecting
    the new implementation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }
