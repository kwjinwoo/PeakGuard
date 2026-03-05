"""Tests for the storage module — PeakRecord dataclass."""

from datetime import date

import pytest

from peakguard.storage import PeakRecord


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
