"""Tests for the storage module — PeakRecord dataclass."""

import json
from datetime import date

import pytest

from peakguard.storage import PeakRecord, deserialize_peaks, serialize_peaks


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
