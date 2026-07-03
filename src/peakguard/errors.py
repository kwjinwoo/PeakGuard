"""Custom exception hierarchy for PeakGuard.

All domain-specific exceptions inherit from PeakGuardError,
allowing callers to catch broad or narrow exception types
as needed.
"""

from enum import Enum

__all__ = [
    "PeakGuardError",
    "FetchError",
    "FetchFailureCause",
    "GistFailureCause",
    "NotificationError",
    "StorageError",
    "GistError",
]


class FetchFailureCause(Enum):
    """Classifies the cause of a fetch failure.

    Members:
        RATE_LIMIT: The external API returned HTTP 429 (Too Many Requests).
        EMPTY_DATA: The API returned no price data for the ticker.
        UNKNOWN: Any other unclassified error.
    """

    RATE_LIMIT = "rate_limit"
    EMPTY_DATA = "empty_data"
    UNKNOWN = "unknown"


class GistFailureCause(Enum):
    """Classifies failures while reading or writing Gist history.

    Members:
        MISSING_FILE: The configured history file is absent from an existing Gist.
        AUTHENTICATION: GitHub rejected the supplied credentials or permissions.
        RATE_LIMIT: GitHub rejected the request because its rate limit was reached.
        NETWORK: The request failed before a valid HTTP response was received.
        MALFORMED_RESPONSE: GitHub returned an unusable JSON response shape.
        MALFORMED_HISTORY: The history file content violates the CSV contract.
        UNKNOWN: Any other unclassified Gist failure.
    """

    MISSING_FILE = "missing_file"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    MALFORMED_RESPONSE = "malformed_response"
    MALFORMED_HISTORY = "malformed_history"
    UNKNOWN = "unknown"


class PeakGuardError(Exception):
    """Base exception for all PeakGuard errors."""


class FetchError(PeakGuardError):
    """Raised when fetching price data from an external source fails.

    Attributes:
        ticker: The ticker symbol that failed to fetch.
        message: A human-readable description of the failure.
        cause: The classified cause of the failure.
    """

    def __init__(
        self,
        *,
        ticker: str,
        message: str,
        cause: FetchFailureCause = FetchFailureCause.UNKNOWN,
    ) -> None:
        self.ticker = ticker
        self.message = message
        self.cause = cause
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
        cause: The classified cause of the failure.
    """

    def __init__(
        self,
        *,
        message: str,
        cause: GistFailureCause = GistFailureCause.UNKNOWN,
    ) -> None:
        self.message = message
        self.cause = cause
        super().__init__(message)
