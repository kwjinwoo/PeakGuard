"""Custom exception hierarchy for PeakGuard.

All domain-specific exceptions inherit from PeakGuardError,
allowing callers to catch broad or narrow exception types
as needed.
"""

__all__ = [
    "PeakGuardError",
    "FetchError",
    "NotificationError",
    "StorageError",
    "GistError",
]


class PeakGuardError(Exception):
    """Base exception for all PeakGuard errors."""


class FetchError(PeakGuardError):
    """Raised when fetching price data from an external source fails.

    Attributes:
        ticker: The ticker symbol that failed to fetch.
        message: A human-readable description of the failure.
    """

    def __init__(self, *, ticker: str, message: str) -> None:
        self.ticker = ticker
        self.message = message
        super().__init__(f"[{ticker}] {message}")


class NotificationError(PeakGuardError):
    """Raised when sending a notification via an external channel fails.

    Attributes:
        message: A human-readable description of the failure.
    """

    def __init__(self, *, message: str) -> None:
        self.message = message
        super().__init__(message)


class StorageError(PeakGuardError):
    """Raised when a storage I/O operation fails.

    Attributes:
        path: The file path involved in the failed operation.
        message: A human-readable description of the failure.
    """

    def __init__(self, *, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"[{path}] {message}")


class GistError(PeakGuardError):
    """Raised when a GitHub Gist API operation fails.

    Attributes:
        message: A human-readable description of the failure.
    """

    def __init__(self, *, message: str) -> None:
        self.message = message
        super().__init__(message)
