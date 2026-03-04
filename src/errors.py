"""Custom exception hierarchy for PeakGuard.

All domain-specific exceptions inherit from PeakGuardError,
allowing callers to catch broad or narrow exception types
as needed.
"""

__all__ = ["PeakGuardError", "FetchError"]


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
