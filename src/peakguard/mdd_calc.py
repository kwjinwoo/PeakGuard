"""MDD calculation module — pure domain logic for Maximum Drawdown tracking.

This module is part of the Domain layer. It contains only pure business
logic for calculating drawdown percentages, evaluating alert thresholds,
and updating all-time high (ATH) records.

No I/O, no network calls, no file system access.
"""

from datetime import date, timedelta
import statistics

from peakguard.storage import ClosingPrice

__all__ = [
    "calculate_days_since_ath",
    "calculate_drawdown",
    "calculate_price_zscore",
    "check_threshold",
    "get_rolling_ath",
    "update_price_history",
]


def calculate_days_since_ath(ath_date: date, today: date) -> int:
    """Calculate the number of calendar days elapsed since the ATH date.

    Args:
        ath_date: The date the all-time high was reached.
        today: The current reference date.

    Returns:
        The number of calendar days between ath_date and today.

    Raises:
        ValueError: If ath_date is later than today.
    """
    if ath_date > today:
        raise ValueError(
            f"ath_date ({ath_date}) must not be later than today ({today})"
        )
    return (today - ath_date).days


def calculate_price_zscore(
    current_price: float, history: list[ClosingPrice]
) -> float:
    """Calculate the Z-score of the current price against the price history.

    Z-score indicates how many standard deviations the current price is
    above or below the mean of the historical prices.

    Args:
        current_price: The latest close price.
        history: A list of ClosingPrice records (at least 2 required).

    Returns:
        The Z-score rounded to 4 decimal places.

    Raises:
        ValueError: If history has fewer than 2 entries, or if all
            prices are identical (standard deviation is zero).
    """
    if len(history) < 2:
        raise ValueError("Need at least 2 price points to compute Z-score")

    prices = [cp.price for cp in history]
    mean = statistics.mean(prices)
    std = statistics.stdev(prices)

    if std == 0:
        raise ValueError("Standard deviation is zero — all prices are identical")

    return round((current_price - mean) / std, 4)


def calculate_drawdown(current_price: float, peak_price: float) -> float:
    """Calculate the drawdown percentage from the all-time high.

    The drawdown represents how far the current price has fallen from
    the recorded peak, expressed as a percentage (0–100).

    Args:
        current_price: The latest close price. Must be positive.
        peak_price: The all-time high price. Must be positive.

    Returns:
        The drawdown percentage, rounded to two decimal places.

    Raises:
        ValueError: If either price is not positive, or if
            current_price exceeds peak_price.
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive, got {current_price}")
    if peak_price <= 0:
        raise ValueError(f"peak_price must be positive, got {peak_price}")
    if current_price > peak_price:
        raise ValueError(
            f"current_price ({current_price}) cannot exceed "
            f"peak_price ({peak_price})"
        )

    return round((peak_price - current_price) / peak_price * 100, 2)


def check_threshold(drawdown_pct: float, threshold: float) -> bool:
    """Determine whether a drawdown has breached the alert threshold.

    The check is inclusive: a drawdown exactly equal to the threshold
    is considered a breach.

    Args:
        drawdown_pct: The current drawdown percentage (0–100).
        threshold: The alert threshold percentage (0 < threshold <= 100).

    Returns:
        True if the drawdown meets or exceeds the threshold.

    Raises:
        ValueError: If drawdown_pct is negative, or threshold is
            not in the range (0, 100].
    """
    if drawdown_pct < 0:
        raise ValueError(f"drawdown_pct must be non-negative, got {drawdown_pct}")
    if threshold <= 0 or threshold > 100:
        raise ValueError(f"threshold must be in the range (0, 100], got {threshold}")

    return drawdown_pct >= threshold


def get_rolling_ath(
    history: list[ClosingPrice], today: date, window_days: int = 365
) -> float:
    """Return the highest price within the rolling window.

    Only prices whose date falls within ``[today - window_days, today]``
    (inclusive on both ends) are considered.

    Args:
        history: A list of ClosingPrice records.
        today: The reference date for the window endpoint.
        window_days: The lookback window size in calendar days.

    Returns:
        The maximum closing price within the window.

    Raises:
        ValueError: If history is empty or no prices fall within the window.
    """
    if not history:
        raise ValueError("history must not be empty")

    cutoff = today - timedelta(days=window_days)
    in_window = [cp for cp in history if cutoff <= cp.date <= today]

    if not in_window:
        raise ValueError(
            f"No prices found within the {window_days}-day window ending {today}"
        )

    return max(cp.price for cp in in_window)


def update_price_history(
    history: list[ClosingPrice],
    *,
    ticker: str,
    price: float,
    today: date,
    window_days: int = 365,
) -> list[ClosingPrice]:
    """Append today's price and trim entries outside the rolling window.

    If an entry for ``today`` already exists, it is replaced (upsert).
    The returned list is sorted by date ascending and contains only
    entries within ``[today - window_days, today]``.

    The original list is not mutated.

    Args:
        history: Existing price history for one ticker.
        ticker: The ticker symbol.
        price: Today's closing price.
        today: The current date.
        window_days: The rolling window size in calendar days.

    Returns:
        A new list of ClosingPrice, trimmed and sorted.
    """
    cutoff = today - timedelta(days=window_days)
    new_entry = ClosingPrice(ticker=ticker, date=today, price=price)

    # Filter: keep entries in window, exclude today (will be re-added)
    kept = [cp for cp in history if cutoff <= cp.date <= today and cp.date != today]
    kept.append(new_entry)
    kept.sort(key=lambda cp: cp.date)

    return kept
