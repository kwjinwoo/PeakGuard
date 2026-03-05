"""Storage module — JSON serialization/deserialization and local file I/O.

This module is part of the Storage layer. It handles conversion between
PeakRecord domain objects and their JSON representation, as well as
reading/writing peak price data to local files.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date

__all__ = ["PeakRecord", "serialize_peaks", "deserialize_peaks"]

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
            raise ValueError(f"peak_price must be positive, got {self.peak_price}")


def serialize_peaks(records: dict[str, "PeakRecord"]) -> str:
    """Serialize peak records to a human-readable JSON string.

    Converts a dict of ticker → PeakRecord into a JSON string with
    sorted keys and 2-space indentation. Dates are formatted as
    ISO 8601 strings.

    Args:
        records: A mapping of ticker symbols to PeakRecord objects.

    Returns:
        A formatted JSON string representing the peak records.
    """
    data = {
        ticker: {
            "peak_price": record.peak_price,
            "peak_date": record.peak_date.isoformat(),
        }
        for ticker, record in records.items()
    }
    return json.dumps(data, indent=2, sort_keys=True)


def deserialize_peaks(data: str) -> dict[str, "PeakRecord"]:
    """Deserialize a JSON string into peak records.

    Parses a JSON string and constructs PeakRecord objects from the data.
    Expects each entry to have ``peak_price`` (float) and ``peak_date``
    (ISO 8601 date string) fields.

    Args:
        data: A JSON string to parse.

    Returns:
        A mapping of ticker symbols to PeakRecord objects.

    Raises:
        ValueError: If the JSON is invalid or required fields are missing.
    """
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    records: dict[str, PeakRecord] = {}
    for ticker, entry in parsed.items():
        try:
            records[ticker] = PeakRecord(
                ticker=ticker,
                peak_price=entry["peak_price"],
                peak_date=date.fromisoformat(entry["peak_date"]),
            )
        except KeyError as exc:
            raise ValueError(
                f"Missing required field {exc} for ticker '{ticker}'"
            ) from exc
    return records
