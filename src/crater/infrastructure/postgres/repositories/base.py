from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class AbstractRepository(ABC, Generic[T]):
    """Generic repository contract for bulk storage operations."""

    @abstractmethod
    async def bulk_insert(self, records: list[T]) -> int:
        """Persist records and return the count of rows written."""

    async def exists(self, key: Any) -> bool:  # noqa: ANN401
        raise NotImplementedError
