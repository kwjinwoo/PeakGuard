"""MDD calculation module — pure domain logic for Maximum Drawdown tracking.

This module is part of the Domain layer. It contains only pure business
logic for calculating drawdown percentages, evaluating alert thresholds,
and updating all-time high (ATH) records.

No I/O, no network calls, no file system access.
"""

__all__ = ["calculate_drawdown"]


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
