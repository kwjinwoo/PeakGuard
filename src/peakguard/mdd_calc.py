"""MDD calculation module — pure domain logic for Maximum Drawdown tracking.

This module is part of the Domain layer. It contains only pure business
logic for calculating drawdown percentages, evaluating alert thresholds,
and updating all-time high (ATH) records.

No I/O, no network calls, no file system access.
"""

from datetime import date

from peakguard.storage import PeakRecord

__all__ = ["calculate_drawdown", "check_threshold", "update_peak"]


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


def update_peak(current_price: float, record: PeakRecord, today: date) -> PeakRecord:
    """Return an updated peak record if the current price is a new ATH.

    If current_price exceeds the stored peak, a new PeakRecord is
    created with the updated price and date. Otherwise, the original
    record is returned unchanged.

    Args:
        current_price: The latest close price. Must be positive.
        record: The existing peak record to compare against.
        today: The date to assign if a new ATH is reached.

    Returns:
        A new PeakRecord if a new ATH is reached, otherwise the
        original record.

    Raises:
        ValueError: If current_price is not positive.
    """
    if current_price <= 0:
        raise ValueError(f"current_price must be positive, got {current_price}")

    if current_price > record.peak_price:
        return PeakRecord(
            ticker=record.ticker,
            peak_price=current_price,
            peak_date=today,
        )

    return record
