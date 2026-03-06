"""Tests for the storage module — ClosingPrice, CSV serialization, and file I/O."""

from datetime import date
from pathlib import Path

import pytest

from peakguard.errors import StorageError
from peakguard.storage import (
    ClosingPrice,
    deserialize_history,
    load_history,
    save_history,
    serialize_history,
)

# ---------------------------------------------------------------------------
# ClosingPrice dataclass
# ---------------------------------------------------------------------------


class TestClosingPrice:
    """Tests for the ClosingPrice dataclass."""

    def test_creation_with_valid_data(self) -> None:
        """Stores all fields correctly."""
        cp = ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50)
        assert cp.ticker == "AAPL"
        assert cp.date == date(2026, 1, 15)
        assert cp.price == 250.50

    def test_is_frozen(self) -> None:
        """ClosingPrice instances are immutable."""
        cp = ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50)
        with pytest.raises(AttributeError):
            cp.price = 300.0  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        """Empty ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            ClosingPrice(ticker="", date=date(2026, 1, 15), price=250.50)

    def test_rejects_whitespace_ticker(self) -> None:
        """Whitespace-only ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            ClosingPrice(ticker="   ", date=date(2026, 1, 15), price=250.50)

    def test_rejects_zero_price(self) -> None:
        """Zero price is invalid → ValueError."""
        with pytest.raises(ValueError, match="price"):
            ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=0.0)

    def test_rejects_negative_price(self) -> None:
        """Negative price is invalid → ValueError."""
        with pytest.raises(ValueError, match="price"):
            ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=-10.0)


# ---------------------------------------------------------------------------
# CSV serialization: serialize_history / deserialize_history
# ---------------------------------------------------------------------------


class TestSerializeHistory:
    """Tests for the serialize_history function."""

    def test_empty_dict_produces_header_only(self) -> None:
        """Empty records produce a CSV with only the header line."""
        result = serialize_history({})
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "ticker,date,price"

    def test_single_ticker_single_entry(self) -> None:
        """Single ticker with one price produces header + one data row."""
        records = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
            ],
        }
        result = serialize_history(records)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert lines[1] == "AAPL,2026-01-15,250.5"

    def test_multiple_tickers_sorted_by_ticker_then_date(self) -> None:
        """Rows are sorted by ticker alphabetically, then by date ascending."""
        records = {
            "MSFT": [
                ClosingPrice(ticker="MSFT", date=date(2026, 2, 20), price=480.00),
                ClosingPrice(ticker="MSFT", date=date(2026, 2, 19), price=475.00),
            ],
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
            ],
        }
        result = serialize_history(records)
        lines = result.strip().split("\n")
        assert len(lines) == 4  # header + 3 data rows
        # AAPL comes before MSFT, MSFT dates sorted ascending
        assert lines[1].startswith("AAPL,")
        assert lines[2].startswith("MSFT,2026-02-19")
        assert lines[3].startswith("MSFT,2026-02-20")

    def test_output_ends_with_newline(self) -> None:
        """CSV output ends with a trailing newline for POSIX compatibility."""
        records = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
            ],
        }
        result = serialize_history(records)
        assert result.endswith("\n")


class TestDeserializeHistory:
    """Tests for the deserialize_history function."""

    def test_header_only_returns_empty_dict(self) -> None:
        """CSV with only header produces empty dict."""
        result = deserialize_history("ticker,date,price\n")
        assert result == {}

    def test_single_row_parses_correctly(self) -> None:
        """Valid single-row CSV is parsed into ClosingPrice."""
        csv_data = "ticker,date,price\nAAPL,2026-01-15,250.5\n"
        result = deserialize_history(csv_data)
        assert len(result) == 1
        assert len(result["AAPL"]) == 1
        assert result["AAPL"][0].ticker == "AAPL"
        assert result["AAPL"][0].date == date(2026, 1, 15)
        assert result["AAPL"][0].price == 250.5

    def test_multiple_tickers_grouped_correctly(self) -> None:
        """Multiple tickers are grouped into separate lists."""
        csv_data = (
            "ticker,date,price\n"
            "AAPL,2026-01-15,250.5\n"
            "MSFT,2026-02-20,480.0\n"
            "AAPL,2026-01-16,252.0\n"
        )
        result = deserialize_history(csv_data)
        assert len(result) == 2
        assert len(result["AAPL"]) == 2
        assert len(result["MSFT"]) == 1

    def test_roundtrip_preserves_data(self) -> None:
        """Serialize then deserialize returns equivalent records."""
        original = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 16), price=252.00),
            ],
            "MSFT": [
                ClosingPrice(ticker="MSFT", date=date(2026, 2, 20), price=480.00),
            ],
        }
        roundtripped = deserialize_history(serialize_history(original))
        assert roundtripped == original

    def test_raises_value_error_on_empty_string(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            deserialize_history("")

    def test_raises_value_error_on_invalid_header(self) -> None:
        """CSV with wrong header raises ValueError."""
        with pytest.raises(ValueError, match="header"):
            deserialize_history("wrong,columns,here\n")

    def test_raises_value_error_on_malformed_row(self) -> None:
        """Row with wrong number of fields raises ValueError."""
        csv_data = "ticker,date,price\nAAPL,2026-01-15\n"
        with pytest.raises(ValueError, match="field"):
            deserialize_history(csv_data)

    def test_raises_value_error_on_invalid_price(self) -> None:
        """Non-numeric price raises ValueError."""
        csv_data = "ticker,date,price\nAAPL,2026-01-15,abc\n"
        with pytest.raises(ValueError, match="price"):
            deserialize_history(csv_data)

    def test_raises_value_error_on_invalid_date(self) -> None:
        """Unparseable date raises ValueError."""
        csv_data = "ticker,date,price\nAAPL,not-a-date,250.5\n"
        with pytest.raises(ValueError, match="date"):
            deserialize_history(csv_data)


# ---------------------------------------------------------------------------
# CSV file I/O: save_history / load_history
# ---------------------------------------------------------------------------


class TestSaveHistory:
    """Tests for the save_history function."""

    def test_writes_csv_file(self, tmp_path: Path) -> None:
        """Happy path: saves history to a CSV file."""
        filepath = tmp_path / "history.csv"
        records = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
            ],
        }
        save_history(records, filepath)

        assert filepath.exists()
        content = filepath.read_text()
        assert "AAPL,2026-01-15,250.5" in content

    def test_writes_header_only_for_empty_dict(self, tmp_path: Path) -> None:
        """Empty records produce a file with only the header."""
        filepath = tmp_path / "history.csv"
        save_history({}, filepath)

        assert filepath.exists()
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "ticker,date,price"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Save overwrites existing file content."""
        filepath = tmp_path / "history.csv"
        filepath.write_text("old data")

        records = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
            ],
        }
        save_history(records, filepath)

        content = filepath.read_text()
        assert "old data" not in content
        assert "AAPL" in content

    def test_raises_storage_error_on_write_failure(self, tmp_path: Path) -> None:
        """I/O failure during write raises StorageError."""
        filepath = tmp_path / "nonexistent_dir" / "sub" / "history.csv"
        records = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
            ],
        }
        with pytest.raises(StorageError, match="history.csv"):
            save_history(records, filepath)


class TestLoadHistory:
    """Tests for the load_history function."""

    def test_loads_records_from_file(self, tmp_path: Path) -> None:
        """Happy path: reads and deserializes a CSV file."""
        filepath = tmp_path / "history.csv"
        filepath.write_text("ticker,date,price\nAAPL,2026-01-15,250.5\n")

        result = load_history(filepath)

        assert len(result) == 1
        assert result["AAPL"][0].ticker == "AAPL"
        assert result["AAPL"][0].price == 250.5

    def test_returns_empty_dict_when_file_missing(self, tmp_path: Path) -> None:
        """Missing file returns empty dict (first-run scenario)."""
        filepath = tmp_path / "nonexistent.csv"
        result = load_history(filepath)
        assert result == {}

    def test_roundtrip_save_then_load(self, tmp_path: Path) -> None:
        """Save then load returns equivalent records."""
        filepath = tmp_path / "history.csv"
        original = {
            "AAPL": [
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 15), price=250.50),
                ClosingPrice(ticker="AAPL", date=date(2026, 1, 16), price=252.00),
            ],
            "MSFT": [
                ClosingPrice(ticker="MSFT", date=date(2026, 2, 20), price=480.00),
            ],
        }
        save_history(original, filepath)
        loaded = load_history(filepath)
        assert loaded == original

    def test_raises_storage_error_on_corrupted_file(self, tmp_path: Path) -> None:
        """Corrupted CSV content raises StorageError."""
        filepath = tmp_path / "bad.csv"
        filepath.write_text("ticker,date,price\nAAPL,bad-date,abc\n")
        with pytest.raises(StorageError, match="bad.csv"):
            load_history(filepath)
