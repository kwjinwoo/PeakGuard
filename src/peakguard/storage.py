"""Storage module — JSON serialization/deserialization and local file I/O.

This module is part of the Storage layer. It handles conversion between
PeakRecord domain objects and their JSON representation, as well as
reading/writing peak price data to local files.
"""

import logging
from dataclasses import dataclass
from datetime import date

__all__ = ["PeakRecord"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PeakRecord:
    """Immutable container for an all-time high (ATH) price record.

    Attributes:
        ticker: The ticker symbol (e.g., "AAPL").
        peak_price: The all-time high price. Must be positive.
        peak_date: The date the ATH was reached.

    Raises:
        ValueError: If ticker is empty or peak_price is not positive.
    """

    ticker: str
    peak_price: float
    peak_date: date

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if self.peak_price <= 0:
            raise ValueError(
                f"peak_price must be positive, got {self.peak_price}"
            )
