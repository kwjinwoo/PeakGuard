"""Tests for the fetcher module — PriceResult, fetch_price, and fetch_prices."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from peakguard.errors import FetchError
from peakguard.fetcher import PriceResult, fetch_price, fetch_prices


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
        mocker.patch("peakguard.fetcher.yfinance.Ticker", return_value=mock_ticker)

        result = fetch_price("AAPL")

        assert isinstance(result, PriceResult)
        assert result.ticker == "AAPL"
        assert result.price == 185.50
        assert result.fetched_at == date(2026, 3, 5)

    def test_raises_fetch_error_on_empty_dataframe(self, mocker) -> None:
        """yfinance returns empty DataFrame (e.g., invalid ticker, no data)."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mocker.patch("peakguard.fetcher.yfinance.Ticker", return_value=mock_ticker)

        with pytest.raises(FetchError, match="INVALID"):
            fetch_price("INVALID")

    def test_wraps_network_exception_in_fetch_error(self, mocker) -> None:
        """Network errors from yfinance are wrapped in FetchError."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = ConnectionError("network down")
        mocker.patch("peakguard.fetcher.yfinance.Ticker", return_value=mock_ticker)

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


class TestFetchPrices:
    """Tests for the fetch_prices function."""

    def test_returns_list_of_price_results(self, mocker) -> None:
        """Happy path: all tickers succeed."""
        histories = {
            "AAPL": (185.50, MagicMock()),
            "MSFT": (420.00, MagicMock()),
        }
        for ticker, (price, mock_obj) in histories.items():
            mock_obj.history.return_value = pd.DataFrame(
                {"Close": [price]},
                index=pd.DatetimeIndex([pd.Timestamp("2026-03-05")]),
            )

        def ticker_factory(symbol):
            return histories[symbol][1]

        mocker.patch("peakguard.fetcher.yfinance.Ticker", side_effect=ticker_factory)

        results = fetch_prices(["AAPL", "MSFT"])

        assert len(results) == 2
        assert results[0].ticker == "AAPL"
        assert results[0].price == 185.50
        assert results[1].ticker == "MSFT"
        assert results[1].price == 420.00

    def test_skips_failed_tickers_and_returns_rest(self, mocker) -> None:
        """One ticker fails but others succeed — no crash."""
        good_mock = MagicMock()
        good_mock.history.return_value = pd.DataFrame(
            {"Close": [185.50]},
            index=pd.DatetimeIndex([pd.Timestamp("2026-03-05")]),
        )
        bad_mock = MagicMock()
        bad_mock.history.return_value = pd.DataFrame()

        def ticker_factory(symbol):
            return good_mock if symbol == "AAPL" else bad_mock

        mocker.patch("peakguard.fetcher.yfinance.Ticker", side_effect=ticker_factory)

        results = fetch_prices(["AAPL", "INVALID"])

        assert len(results) == 1
        assert results[0].ticker == "AAPL"

    def test_returns_empty_list_when_all_fail(self, mocker) -> None:
        """All tickers fail — returns empty list, no crash."""
        bad_mock = MagicMock()
        bad_mock.history.return_value = pd.DataFrame()
        mocker.patch("peakguard.fetcher.yfinance.Ticker", return_value=bad_mock)

        results = fetch_prices(["INVALID1", "INVALID2"])

        assert results == []

    def test_returns_empty_list_for_empty_input(self) -> None:
        """Empty ticker list returns empty result list."""
        results = fetch_prices([])
        assert results == []
