"""Tests for the mdd_calc module — pure domain logic for MDD tracking."""

import pytest

from peakguard.mdd_calc import calculate_drawdown


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
