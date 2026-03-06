"""Storage module — serialization/deserialization and local file I/O.

This module is part of the Storage layer. It handles conversion between
domain objects and their serialized representation (JSON for PeakRecord,
CSV for ClosingPrice), as well as reading/writing data to local files.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from peakguard.errors import StorageError

__all__ = [
    "ClosingPrice",
    "PeakRecord",
    "deserialize_history",
    "deserialize_peaks",
    "load_history",
    "load_peaks",
    "save_history",
    "save_peaks",
    "serialize_history",
    "serialize_peaks",
]

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


def save_peaks(records: dict[str, "PeakRecord"], path: Path) -> None:
    """Save peak records to a local JSON file.

    Serializes the records to a human-readable JSON string and writes
    it to the specified file path. Overwrites any existing content.

    Args:
        records: A mapping of ticker symbols to PeakRecord objects.
        path: The file path to write to.

    Raises:
        StorageError: If the file cannot be written.
    """
    try:
        path.write_text(serialize_peaks(records), encoding="utf-8")
    except OSError as exc:
        raise StorageError(path=str(path), message=str(exc)) from exc


def load_peaks(path: Path) -> dict[str, "PeakRecord"]:
    """Load peak records from a local JSON file.

    If the file does not exist, returns an empty dict (first-run scenario).

    Args:
        path: The file path to read from.

    Returns:
        A mapping of ticker symbols to PeakRecord objects.

    Raises:
        StorageError: If the file exists but cannot be read or parsed.
    """
    if not path.exists():
        logger.info("Peak file not found at %s, returning empty records", path)
        return {}

    try:
        data = path.read_text(encoding="utf-8")
        return deserialize_peaks(data)
    except (OSError, ValueError) as exc:
        raise StorageError(path=str(path), message=str(exc)) from exc


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
