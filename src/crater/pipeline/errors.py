from __future__ import annotations


class CraterError(Exception):
    """Base exception for all Crater pipeline errors."""


class TruncatedResponseError(CraterError):
    """Raised when the vendor response is shorter than its declared Content-Length."""

    def __init__(self, filename: str, expected: int, received: int) -> None:
        self.filename = filename
        self.expected = expected
        self.received = received
        super().__init__(
            f"{filename}: truncated — received {received} bytes, expected {expected}"
        )


class VendorOutageError(CraterError):
    """Raised when the vendor responds with 503 (outage window active)."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        super().__init__(f"{filename}: vendor outage (503)")


class GzipDecompressionError(CraterError):
    """Raised when a downloaded file cannot be decompressed at all."""

    def __init__(self, filename: str, cause: Exception) -> None:
        self.filename = filename
        self.cause = cause
        super().__init__(f"{filename}: gzip decompression failed — {cause}")


class WatermarkError(CraterError):
    """Raised on failure to read or write the high-water mark."""


class RepositoryError(CraterError):
    """Raised when a database repository operation fails."""
