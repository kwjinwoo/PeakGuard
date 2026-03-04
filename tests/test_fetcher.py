"""Tests for the fetcher module — PriceResult and fetch_price."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from errors import FetchError
from fetcher import PriceResult, fetch_price


class TestPriceResult:
    """Tests for the PriceResult dataclass."""

    def test_creation_with_valid_data(self) -> None:
        result = PriceResult(ticker="AAPL", price=150.0, fetched_at=date(2026, 3, 5))
        assert result.ticker == "AAPL"
        assert result.price == 150.0
        assert result.fetched_at == date(2026, 3, 5)

    def test_is_frozen(self) -> None:
        result = PriceResult(ticker="AAPL", price=150.0, fetched_at=date(2026, 3, 5))
        with pytest.raises(AttributeError):
            result.price = 200.0  # type: ignore[misc]

    def test_rejects_zero_price(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PriceResult(ticker="AAPL", price=0.0, fetched_at=date(2026, 3, 5))

    def test_rejects_negative_price(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PriceResult(ticker="AAPL", price=-10.0, fetched_at=date(2026, 3, 5))


class TestFetchPrice:
    """Tests for the fetch_price function."""

    def test_returns_price_result_on_success(self, mocker) -> None:
        """Happy path: yfinance returns valid data."""
        mock_history = pd.DataFrame(
            {"Close": [185.50]},
            index=pd.DatetimeIndex([pd.Timestamp("2026-03-05")]),
        )
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_history
        mocker.patch("fetcher.yfinance.Ticker", return_value=mock_ticker)

        result = fetch_price("AAPL")

        assert isinstance(result, PriceResult)
        assert result.ticker == "AAPL"
        assert result.price == 185.50
        assert result.fetched_at == date(2026, 3, 5)

    def test_raises_fetch_error_on_empty_dataframe(self, mocker) -> None:
        """yfinance returns empty DataFrame (e.g., invalid ticker, no data)."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mocker.patch("fetcher.yfinance.Ticker", return_value=mock_ticker)

        with pytest.raises(FetchError, match="INVALID"):
            fetch_price("INVALID")

    def test_wraps_network_exception_in_fetch_error(self, mocker) -> None:
        """Network errors from yfinance are wrapped in FetchError."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = ConnectionError("network down")
        mocker.patch("fetcher.yfinance.Ticker", return_value=mock_ticker)

        with pytest.raises(FetchError, match="MSFT") as exc_info:
            fetch_price("MSFT")
        assert "network down" in str(exc_info.value)

    def test_raises_value_error_on_empty_ticker(self) -> None:
        """Empty ticker string is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            fetch_price("")

    def test_raises_value_error_on_whitespace_ticker(self) -> None:
        """Whitespace-only ticker string is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            fetch_price("   ")
