"""Tests for the mdd_calc module — pure domain logic for MDD tracking."""

from datetime import date, timedelta

import pytest

from peakguard.mdd_calc import (
    calculate_drawdown,
    check_threshold,
    get_rolling_ath,
    update_price_history,
)
from peakguard.storage import ClosingPrice


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


# ---------------------------------------------------------------------------
# Rolling window ATH: get_rolling_ath
# ---------------------------------------------------------------------------


class TestGetRollingAth:
    """Tests for the get_rolling_ath function."""

    @staticmethod
    def _make_history(
        ticker: str = "AAPL",
        prices_and_dates: list[tuple[date, float]] | None = None,
    ) -> list[ClosingPrice]:
        if prices_and_dates is None:
            prices_and_dates = [
                (date(2025, 6, 1), 150.0),
                (date(2025, 9, 1), 200.0),
                (date(2025, 12, 1), 180.0),
                (date(2026, 3, 1), 190.0),
            ]
        return [
            ClosingPrice(ticker=ticker, date=d, price=p) for d, p in prices_and_dates
        ]

    def test_returns_max_price_within_window(self) -> None:
        """Rolling ATH is the highest price within the window."""
        history = self._make_history()
        today = date(2026, 3, 6)

        result = get_rolling_ath(history, today, window_days=365)

        assert result == 200.0

    def test_excludes_prices_outside_window(self) -> None:
        """Prices older than window_days are excluded."""
        history = self._make_history(
            prices_and_dates=[
                (date(2024, 1, 1), 500.0),  # >365 days ago from today
                (date(2025, 6, 1), 150.0),
                (date(2025, 12, 1), 180.0),
            ]
        )
        today = date(2026, 3, 6)

        result = get_rolling_ath(history, today, window_days=365)

        assert result == 180.0  # 500.0 is excluded

    def test_boundary_date_is_included(self) -> None:
        """Price exactly at window boundary (365 days ago) is included."""
        today = date(2026, 3, 6)
        boundary_date = today - timedelta(days=365)
        history = self._make_history(
            prices_and_dates=[
                (boundary_date, 300.0),
                (date(2026, 3, 1), 200.0),
            ]
        )

        result = get_rolling_ath(history, today, window_days=365)

        assert result == 300.0

    def test_raises_value_error_on_empty_history(self) -> None:
        """Empty history raises ValueError."""
        with pytest.raises(ValueError, match="history"):
            get_rolling_ath([], date(2026, 3, 6))

    def test_raises_value_error_when_no_prices_in_window(self) -> None:
        """All prices outside window raises ValueError."""
        history = self._make_history(
            prices_and_dates=[
                (date(2024, 1, 1), 500.0),
            ]
        )
        with pytest.raises(ValueError, match="window"):
            get_rolling_ath(history, date(2026, 3, 6), window_days=365)

    def test_custom_window_days(self) -> None:
        """Custom window_days narrows the lookback."""
        history = self._make_history(
            prices_and_dates=[
                (date(2026, 1, 1), 300.0),
                (date(2026, 2, 1), 250.0),
                (date(2026, 3, 1), 200.0),
            ]
        )
        today = date(2026, 3, 6)

        # 30-day window excludes Jan 1 and Feb 1
        result = get_rolling_ath(history, today, window_days=30)

        assert result == 200.0


# ---------------------------------------------------------------------------
# Rolling window ATH: update_price_history
# ---------------------------------------------------------------------------


class TestUpdatePriceHistory:
    """Tests for the update_price_history function."""

    def test_appends_new_entry(self) -> None:
        """New price is appended to history."""
        history = [
            ClosingPrice(ticker="AAPL", date=date(2026, 3, 5), price=190.0),
        ]
        today = date(2026, 3, 6)

        result = update_price_history(history, ticker="AAPL", price=195.0, today=today)

        assert len(result) == 2
        assert result[-1].price == 195.0
        assert result[-1].date == today

    def test_upsert_same_date_overwrites(self) -> None:
        """Existing entry for same date is replaced (upsert)."""
        history = [
            ClosingPrice(ticker="AAPL", date=date(2026, 3, 6), price=190.0),
        ]

        result = update_price_history(
            history, ticker="AAPL", price=195.0, today=date(2026, 3, 6)
        )

        assert len(result) == 1
        assert result[0].price == 195.0

    def test_trims_entries_older_than_window(self) -> None:
        """Entries older than window_days are removed."""
        today = date(2026, 3, 6)
        old_date = today - timedelta(days=366)
        history = [
            ClosingPrice(ticker="AAPL", date=old_date, price=300.0),
            ClosingPrice(ticker="AAPL", date=date(2026, 3, 5), price=190.0),
        ]

        result = update_price_history(
            history, ticker="AAPL", price=195.0, today=today, window_days=365
        )

        assert len(result) == 2  # old entry removed, new one added
        dates = [cp.date for cp in result]
        assert old_date not in dates

    def test_result_sorted_by_date_ascending(self) -> None:
        """Returned list is always sorted by date ascending."""
        history = [
            ClosingPrice(ticker="AAPL", date=date(2026, 3, 5), price=190.0),
            ClosingPrice(ticker="AAPL", date=date(2026, 3, 3), price=185.0),
        ]

        result = update_price_history(
            history, ticker="AAPL", price=195.0, today=date(2026, 3, 6)
        )

        dates = [cp.date for cp in result]
        assert dates == sorted(dates)

    def test_empty_history_creates_single_entry(self) -> None:
        """Empty history results in a single-entry list."""
        result = update_price_history(
            [], ticker="AAPL", price=195.0, today=date(2026, 3, 6)
        )

        assert len(result) == 1
        assert result[0].price == 195.0
        assert result[0].date == date(2026, 3, 6)

    def test_does_not_mutate_original_list(self) -> None:
        """Original history list is not modified."""
        history = [
            ClosingPrice(ticker="AAPL", date=date(2026, 3, 5), price=190.0),
        ]
        original_len = len(history)

        update_price_history(
            history, ticker="AAPL", price=195.0, today=date(2026, 3, 6)
        )

        assert len(history) == original_len
