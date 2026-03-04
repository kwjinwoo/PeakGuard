"""Fetcher module — wraps yfinance to retrieve latest close prices.

This module is part of the External Services layer. It handles
all interaction with the yfinance library and converts raw data
into domain-friendly PriceResult objects.
"""

from dataclasses import dataclass
from datetime import date

import yfinance

from errors import FetchError


@dataclass(frozen=True)
class PriceResult:
    """Immutable container for a fetched price data point.

    Attributes:
        ticker: The ticker symbol (e.g., "AAPL").
        price: The latest close price. Must be positive.
        fetched_at: The date of the price data point.

    Raises:
        ValueError: If price is not positive.
    """

    ticker: str
    price: float
    fetched_at: date

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError(f"price must be positive, got {self.price}")


def fetch_price(ticker: str) -> PriceResult:
    """Fetch the latest close price for a single ticker.

    Args:
        ticker: A non-empty ticker symbol string (e.g., "AAPL").

    Returns:
        A PriceResult containing the ticker, close price, and date.

    Raises:
        ValueError: If ticker is empty or whitespace-only (programmer error).
        FetchError: If the price data cannot be retrieved from yfinance.
    """
    if not ticker or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")

    try:
        yf_ticker = yfinance.Ticker(ticker)
        history = yf_ticker.history(period="1d")
    except Exception as exc:
        raise FetchError(ticker=ticker, message=str(exc)) from exc

    if history.empty:
        raise FetchError(ticker=ticker, message="no price data returned")

    last_row = history.iloc[-1]
    close_price: float = float(last_row["Close"])
    trade_date: date = history.index[-1].date()

    return PriceResult(ticker=ticker, price=close_price, fetched_at=trade_date)
