"""Tests for the mdd_calc module — pure domain logic for MDD tracking."""

from datetime import date

import pytest

from peakguard.mdd_calc import calculate_drawdown, check_threshold, update_peak
from peakguard.storage import PeakRecord


class TestCalculateDrawdown:
    """Tests for the calculate_drawdown function."""

    def test_typical_drawdown(self) -> None:
        """20 % drop from peak returns 20.0."""
        assert calculate_drawdown(current_price=80.0, peak_price=100.0) == 20.0

    def test_no_drawdown_when_at_peak(self) -> None:
        """Price at ATH returns 0.0."""
        assert calculate_drawdown(current_price=100.0, peak_price=100.0) == 0.0

    def test_small_drawdown(self) -> None:
        """Fractional drop is rounded to two decimal places."""
        assert calculate_drawdown(current_price=99.5, peak_price=100.0) == 0.5

    def test_large_drawdown(self) -> None:
        """90 % drop from peak returns 90.0."""
        assert calculate_drawdown(current_price=10.0, peak_price=100.0) == 90.0

    def test_rounding_to_two_decimals(self) -> None:
        """Result is rounded to two decimal places."""
        # 1/3 drop ≈ 33.333… → 33.33
        result = calculate_drawdown(current_price=200.0, peak_price=300.0)
        assert result == 33.33

    def test_rejects_zero_current_price(self) -> None:
        """Zero current_price is invalid → ValueError."""
        with pytest.raises(ValueError, match="current_price"):
            calculate_drawdown(current_price=0.0, peak_price=100.0)

    def test_rejects_negative_current_price(self) -> None:
        """Negative current_price is invalid → ValueError."""
        with pytest.raises(ValueError, match="current_price"):
            calculate_drawdown(current_price=-5.0, peak_price=100.0)

    def test_rejects_zero_peak_price(self) -> None:
        """Zero peak_price is invalid → ValueError."""
        with pytest.raises(ValueError, match="peak_price"):
            calculate_drawdown(current_price=80.0, peak_price=0.0)

    def test_rejects_negative_peak_price(self) -> None:
        """Negative peak_price is invalid → ValueError."""
        with pytest.raises(ValueError, match="peak_price"):
            calculate_drawdown(current_price=80.0, peak_price=-10.0)

    def test_rejects_current_exceeding_peak(self) -> None:
        """current_price > peak_price is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="cannot exceed"):
            calculate_drawdown(current_price=110.0, peak_price=100.0)


class TestCheckThreshold:
    """Tests for the check_threshold function."""

    def test_drawdown_exceeds_threshold(self) -> None:
        """Drawdown above threshold triggers alert."""
        assert check_threshold(drawdown_pct=15.0, threshold=10.0) is True

    def test_drawdown_below_threshold(self) -> None:
        """Drawdown below threshold does not trigger alert."""
        assert check_threshold(drawdown_pct=5.0, threshold=10.0) is False

    def test_drawdown_exactly_at_threshold(self) -> None:
        """Drawdown exactly at threshold triggers alert (boundary inclusive)."""
        assert check_threshold(drawdown_pct=10.0, threshold=10.0) is True

    def test_zero_drawdown(self) -> None:
        """Zero drawdown does not trigger alert."""
        assert check_threshold(drawdown_pct=0.0, threshold=5.0) is False

    def test_rejects_negative_drawdown(self) -> None:
        """Negative drawdown_pct is invalid → ValueError."""
        with pytest.raises(ValueError, match="drawdown_pct"):
            check_threshold(drawdown_pct=-1.0, threshold=10.0)

    def test_rejects_zero_threshold(self) -> None:
        """Zero threshold is invalid → ValueError."""
        with pytest.raises(ValueError, match="threshold"):
            check_threshold(drawdown_pct=5.0, threshold=0.0)

    def test_rejects_negative_threshold(self) -> None:
        """Negative threshold is invalid → ValueError."""
        with pytest.raises(ValueError, match="threshold"):
            check_threshold(drawdown_pct=5.0, threshold=-5.0)

    def test_rejects_threshold_above_100(self) -> None:
        """Threshold > 100 is invalid → ValueError."""
        with pytest.raises(ValueError, match="threshold"):
            check_threshold(drawdown_pct=5.0, threshold=101.0)


class TestUpdatePeak:
    """Tests for the update_peak function."""

    @staticmethod
    def _make_record(
        ticker: str = "AAPL",
        peak_price: float = 100.0,
        peak_date: date = date(2026, 1, 15),
    ) -> PeakRecord:
        return PeakRecord(ticker=ticker, peak_price=peak_price, peak_date=peak_date)

    def test_new_ath_returns_updated_record(self) -> None:
        """Price above ATH produces a new PeakRecord with updated price and date."""
        record = self._make_record(peak_price=100.0)
        today = date(2026, 3, 6)

        result = update_peak(current_price=110.0, record=record, today=today)

        assert result.peak_price == 110.0
        assert result.peak_date == today
        assert result.ticker == "AAPL"

    def test_same_price_keeps_original_record(self) -> None:
        """Price equal to ATH returns the original record unchanged."""
        record = self._make_record(peak_price=100.0)
        today = date(2026, 3, 6)

        result = update_peak(current_price=100.0, record=record, today=today)

        assert result is record

    def test_lower_price_keeps_original_record(self) -> None:
        """Price below ATH returns the original record unchanged."""
        record = self._make_record(peak_price=100.0)
        today = date(2026, 3, 6)

        result = update_peak(current_price=90.0, record=record, today=today)

        assert result is record

    def test_preserves_ticker(self) -> None:
        """Updated record preserves the original ticker symbol."""
        record = self._make_record(ticker="MSFT", peak_price=400.0)
        today = date(2026, 3, 6)

        result = update_peak(current_price=450.0, record=record, today=today)

        assert result.ticker == "MSFT"

    def test_rejects_zero_current_price(self) -> None:
        """Zero current_price is invalid → ValueError."""
        record = self._make_record()
        with pytest.raises(ValueError, match="current_price"):
            update_peak(current_price=0.0, record=record, today=date(2026, 3, 6))

    def test_rejects_negative_current_price(self) -> None:
        """Negative current_price is invalid → ValueError."""
        record = self._make_record()
        with pytest.raises(ValueError, match="current_price"):
            update_peak(current_price=-5.0, record=record, today=date(2026, 3, 6))
