"""Tests for the storage module — PeakRecord, serialization, and file I/O."""

import json
from datetime import date
from pathlib import Path

import pytest

from peakguard.errors import StorageError
from peakguard.storage import (
    PeakRecord,
    deserialize_peaks,
    load_peaks,
    save_peaks,
    serialize_peaks,
)


class TestPeakRecord:
    """Tests for the PeakRecord dataclass."""

    def test_creation_with_valid_data(self) -> None:
        """Stores all fields correctly."""
        record = PeakRecord(
            ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
        )
        assert record.ticker == "AAPL"
        assert record.peak_price == 250.50
        assert record.peak_date == date(2026, 1, 15)

    def test_is_frozen(self) -> None:
        """PeakRecord instances are immutable."""
        record = PeakRecord(
            ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
        )
        with pytest.raises(AttributeError):
            record.peak_price = 300.0  # type: ignore[misc]

    def test_rejects_zero_price(self) -> None:
        """Zero peak_price is invalid → ValueError."""
        with pytest.raises(ValueError, match="peak_price"):
            PeakRecord(ticker="AAPL", peak_price=0.0, peak_date=date(2026, 1, 15))

    def test_rejects_negative_price(self) -> None:
        """Negative peak_price is invalid → ValueError."""
        with pytest.raises(ValueError, match="peak_price"):
            PeakRecord(ticker="AAPL", peak_price=-10.0, peak_date=date(2026, 1, 15))

    def test_rejects_empty_ticker(self) -> None:
        """Empty ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            PeakRecord(ticker="", peak_price=250.50, peak_date=date(2026, 1, 15))

    def test_rejects_whitespace_ticker(self) -> None:
        """Whitespace-only ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            PeakRecord(ticker="   ", peak_price=250.50, peak_date=date(2026, 1, 15))


class TestSerializePeaks:
    """Tests for the serialize_peaks function."""

    def test_empty_dict_serializes_to_empty_json(self) -> None:
        """Empty records produce an empty JSON object."""
        result = serialize_peaks({})
        assert json.loads(result) == {}

    def test_single_record_serializes_correctly(self) -> None:
        """Single PeakRecord is serialized with ticker as key."""
        records = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
        }
        result = serialize_peaks(records)
        parsed = json.loads(result)
        assert parsed == {
            "AAPL": {"peak_price": 250.50, "peak_date": "2026-01-15"},
        }

    def test_multiple_records_serialized_with_sorted_keys(self) -> None:
        """Multiple records are serialized with keys sorted alphabetically."""
        records = {
            "MSFT": PeakRecord(
                ticker="MSFT", peak_price=480.00, peak_date=date(2026, 2, 20)
            ),
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
        }
        result = serialize_peaks(records)
        keys = list(json.loads(result).keys())
        assert keys == ["AAPL", "MSFT"]

    def test_output_is_human_readable(self) -> None:
        """JSON output uses indentation for readability."""
        records = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
        }
        result = serialize_peaks(records)
        assert "\n" in result
        assert "  " in result


class TestDeserializePeaks:
    """Tests for the deserialize_peaks function."""

    def test_empty_json_deserializes_to_empty_dict(self) -> None:
        """Empty JSON object produces empty records dict."""
        result = deserialize_peaks("{}")
        assert result == {}

    def test_single_record_deserializes_correctly(self) -> None:
        """Valid JSON is deserialized into PeakRecord objects."""
        data = json.dumps({"AAPL": {"peak_price": 250.50, "peak_date": "2026-01-15"}})
        result = deserialize_peaks(data)
        assert len(result) == 1
        assert result["AAPL"].ticker == "AAPL"
        assert result["AAPL"].peak_price == 250.50
        assert result["AAPL"].peak_date == date(2026, 1, 15)

    def test_roundtrip_preserves_data(self) -> None:
        """Serialize then deserialize returns equivalent records."""
        original = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
            "MSFT": PeakRecord(
                ticker="MSFT", peak_price=480.00, peak_date=date(2026, 2, 20)
            ),
        }
        roundtripped = deserialize_peaks(serialize_peaks(original))
        assert roundtripped == original

    def test_raises_value_error_on_invalid_json(self) -> None:
        """Invalid JSON string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            deserialize_peaks("not valid json")

    def test_raises_value_error_on_missing_field(self) -> None:
        """Missing required field in JSON raises ValueError."""
        data = json.dumps({"AAPL": {"peak_price": 250.50}})
        with pytest.raises(ValueError, match="peak_date"):
            deserialize_peaks(data)


class TestSavePeaks:
    """Tests for the save_peaks function."""

    def test_writes_json_file(self, tmp_path: Path) -> None:
        """Happy path: saves records to a JSON file."""
        filepath = tmp_path / "peak_prices.json"
        records = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
        }
        save_peaks(records, filepath)

        assert filepath.exists()
        parsed = json.loads(filepath.read_text())
        assert parsed["AAPL"]["peak_price"] == 250.50
        assert parsed["AAPL"]["peak_date"] == "2026-01-15"

    def test_writes_empty_json_for_empty_dict(self, tmp_path: Path) -> None:
        """Empty records produce an empty JSON object file."""
        filepath = tmp_path / "peak_prices.json"
        save_peaks({}, filepath)

        assert filepath.exists()
        assert json.loads(filepath.read_text()) == {}

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Saves overwrite existing file content."""
        filepath = tmp_path / "peak_prices.json"
        filepath.write_text('{"OLD": {}}')

        records = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
        }
        save_peaks(records, filepath)

        parsed = json.loads(filepath.read_text())
        assert "OLD" not in parsed
        assert "AAPL" in parsed

    def test_raises_storage_error_on_write_failure(self, tmp_path: Path) -> None:
        """I/O failure during write raises StorageError."""
        filepath = tmp_path / "nonexistent_dir" / "sub" / "peak_prices.json"
        records = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
        }
        with pytest.raises(StorageError, match="peak_prices.json"):
            save_peaks(records, filepath)


class TestLoadPeaks:
    """Tests for the load_peaks function."""

    def test_loads_records_from_file(self, tmp_path: Path) -> None:
        """Happy path: reads and deserializes a JSON file."""
        filepath = tmp_path / "peak_prices.json"
        data = json.dumps({"AAPL": {"peak_price": 250.50, "peak_date": "2026-01-15"}})
        filepath.write_text(data)

        result = load_peaks(filepath)

        assert len(result) == 1
        assert result["AAPL"].ticker == "AAPL"
        assert result["AAPL"].peak_price == 250.50
        assert result["AAPL"].peak_date == date(2026, 1, 15)

    def test_returns_empty_dict_when_file_missing(self, tmp_path: Path) -> None:
        """Missing file returns empty dict (first run scenario)."""
        filepath = tmp_path / "nonexistent.json"
        result = load_peaks(filepath)
        assert result == {}

    def test_roundtrip_save_then_load(self, tmp_path: Path) -> None:
        """Save then load returns equivalent records."""
        filepath = tmp_path / "peak_prices.json"
        original = {
            "AAPL": PeakRecord(
                ticker="AAPL", peak_price=250.50, peak_date=date(2026, 1, 15)
            ),
            "MSFT": PeakRecord(
                ticker="MSFT", peak_price=480.00, peak_date=date(2026, 2, 20)
            ),
        }
        save_peaks(original, filepath)
        loaded = load_peaks(filepath)
        assert loaded == original

    def test_raises_storage_error_on_read_failure(self, tmp_path: Path) -> None:
        """Corrupted file content raises StorageError."""
        filepath = tmp_path / "bad.json"
        filepath.write_text("not valid json")
        with pytest.raises(StorageError, match="bad.json"):
            load_peaks(filepath)
