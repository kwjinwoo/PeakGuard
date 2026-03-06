"""Storage module — serialization/deserialization and local file I/O.

This module is part of the Storage layer. It handles conversion between
domain objects and their CSV serialized representation, as well as
reading/writing data to local files.
"""

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from peakguard.errors import StorageError

__all__ = [
    "ClosingPrice",
    "deserialize_history",
    "load_history",
    "save_history",
    "serialize_history",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ClosingPrice — daily close price record for rolling-window ATH tracking
# ---------------------------------------------------------------------------

_CSV_HEADER = "ticker,date,price"


@dataclass(frozen=True)
class ClosingPrice:
    """Immutable container for a single daily closing price.

    Attributes:
        ticker: The ticker symbol (e.g., "AAPL").
        date: The trading date.
        price: The closing price. Must be positive.

    Raises:
        ValueError: If ticker is empty or price is not positive.
    """

    ticker: str
    date: date
    price: float

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")


def serialize_history(records: dict[str, list["ClosingPrice"]]) -> str:
    """Serialize price history to a CSV string.

    Rows are sorted by ticker alphabetically, then by date ascending.
    The output always starts with the header ``ticker,date,price``
    and ends with a trailing newline.

    Args:
        records: A mapping of ticker symbols to lists of ClosingPrice.

    Returns:
        A CSV string with header and data rows.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["ticker", "date", "price"])

    for ticker in sorted(records.keys()):
        for cp in sorted(records[ticker], key=lambda c: c.date):
            writer.writerow([cp.ticker, cp.date.isoformat(), cp.price])

    return buf.getvalue()


def deserialize_history(data: str) -> dict[str, list["ClosingPrice"]]:
    """Deserialize a CSV string into price history records.

    Expects a CSV with columns ``ticker``, ``date``, ``price``.
    Rows are grouped by ticker and sorted by date ascending.

    Args:
        data: A CSV string to parse.

    Returns:
        A mapping of ticker symbols to lists of ClosingPrice,
        each list sorted by date ascending.

    Raises:
        ValueError: If the CSV is empty, has an invalid header,
            or contains malformed rows.
    """
    if not data or not data.strip():
        raise ValueError("CSV data is empty")

    lines = data.strip().split("\n")
    header = lines[0].strip()
    if header != _CSV_HEADER:
        raise ValueError(
            f"Invalid CSV header: expected '{_CSV_HEADER}', got '{header}'"
        )

    records: dict[str, list[ClosingPrice]] = {}
    for i, line in enumerate(lines[1:], start=2):
        parts = line.strip().split(",")
        if len(parts) != 3:
            raise ValueError(f"Row {i}: expected 3 fields, got {len(parts)}")

        ticker_val, date_str, price_str = parts

        try:
            date_val = date.fromisoformat(date_str)
        except ValueError as exc:
            raise ValueError(f"Row {i}: invalid date '{date_str}'") from exc

        try:
            price_val = float(price_str)
        except ValueError as exc:
            raise ValueError(f"Row {i}: invalid price '{price_str}'") from exc

        cp = ClosingPrice(ticker=ticker_val, date=date_val, price=price_val)
        records.setdefault(ticker_val, []).append(cp)

    # Sort each ticker's entries by date ascending
    for ticker_val in records:
        records[ticker_val].sort(key=lambda c: c.date)

    return records


def save_history(records: dict[str, list["ClosingPrice"]], path: Path) -> None:
    """Save price history to a local CSV file.

    Args:
        records: A mapping of ticker symbols to lists of ClosingPrice.
        path: The file path to write to.

    Raises:
        StorageError: If the file cannot be written.
    """
    try:
        path.write_text(serialize_history(records), encoding="utf-8")
    except OSError as exc:
        raise StorageError(path=str(path), message=str(exc)) from exc


def load_history(path: Path) -> dict[str, list["ClosingPrice"]]:
    """Load price history from a local CSV file.

    If the file does not exist, returns an empty dict (first-run scenario).

    Args:
        path: The file path to read from.

    Returns:
        A mapping of ticker symbols to lists of ClosingPrice.

    Raises:
        StorageError: If the file exists but cannot be read or parsed.
    """
    if not path.exists():
        logger.info("History file not found at %s, returning empty records", path)
        return {}

    try:
        data = path.read_text(encoding="utf-8")
        return deserialize_history(data)
    except (OSError, ValueError) as exc:
        raise StorageError(path=str(path), message=str(exc)) from exc
