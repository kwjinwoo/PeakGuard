"""Fetcher module — wraps yfinance to retrieve latest close prices.

This module is part of the External Services layer. It handles
all interaction with the yfinance library and converts raw data
into domain-friendly PriceResult objects.
"""

import logging
from dataclasses import dataclass
from datetime import date

import requests
import yfinance

from peakguard.errors import FetchError, FetchFailureCause
from peakguard.storage import ClosingPrice

__all__ = ["PriceResult", "fetch_history", "fetch_price", "fetch_prices"]

logger = logging.getLogger(__name__)


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


def _classify_cause(exc: Exception) -> FetchFailureCause:
    """Classify the cause of a fetch failure from exception type.

    Args:
        exc: The exception raised during fetch.

    Returns:
        The classified FetchFailureCause.
    """
    if (
        isinstance(exc, requests.exceptions.HTTPError)
        and hasattr(exc, "response")
        and exc.response is not None
        and exc.response.status_code == 429
    ):
        return FetchFailureCause.RATE_LIMIT
    return FetchFailureCause.UNKNOWN


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
        cause = _classify_cause(exc)
        raise FetchError(ticker=ticker, message=str(exc), cause=cause) from exc

    if history.empty:
        raise FetchError(
            ticker=ticker,
            message="no price data returned",
            cause=FetchFailureCause.EMPTY_DATA,
        )

    last_row = history.iloc[-1]
    close_price: float = float(last_row["Close"])
    trade_date: date = history.index[-1].date()

    return PriceResult(ticker=ticker, price=close_price, fetched_at=trade_date)


def fetch_history(ticker: str, period: str = "1y") -> list[ClosingPrice]:
    """Fetch historical close prices for a single ticker.

    Used for bootstrap: when a ticker has no prior history stored,
    this function fetches a full year of daily close prices in one
    call to minimize future API usage.

    Args:
        ticker: A non-empty ticker symbol string (e.g., "AAPL").
        period: The yfinance period string (default: "1y").

    Returns:
        A list of ClosingPrice sorted by date ascending.

    Raises:
        ValueError: If ticker is empty or whitespace-only (programmer error).
        FetchError: If the price data cannot be retrieved from yfinance.
    """
    if not ticker or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")

    try:
        yf_ticker = yfinance.Ticker(ticker)
        history = yf_ticker.history(period=period)
    except Exception as exc:
        cause = _classify_cause(exc)
        raise FetchError(ticker=ticker, message=str(exc), cause=cause) from exc

    if history.empty:
        raise FetchError(
            ticker=ticker,
            message="no price data returned",
            cause=FetchFailureCause.EMPTY_DATA,
        )

    results: list[ClosingPrice] = []
    for idx, row in history.iterrows():
        results.append(
            ClosingPrice(
                ticker=ticker,
                date=idx.date(),
                price=float(row["Close"]),
            )
        )

    results.sort(key=lambda cp: cp.date)
    return results


def fetch_prices(tickers: list[str]) -> list[PriceResult]:
    """Fetch the latest close prices for multiple tickers.

    Iterates through each ticker and calls fetch_price individually.
    If a single ticker fails, the error is logged and that ticker
    is skipped — the remaining tickers are still processed.

    Args:
        tickers: A list of ticker symbol strings.

    Returns:
        A list of PriceResult for each successfully fetched ticker.
        May be shorter than the input list if some tickers failed.
    """
    results: list[PriceResult] = []
    for ticker in tickers:
        try:
            results.append(fetch_price(ticker))
        except FetchError as exc:
            logger.warning("Failed to fetch %s: %s", ticker, exc)
    return results
