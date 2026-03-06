"""Tests for main module — rolling window ATH orchestration logic."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from peakguard.config import TickerConfig
from peakguard.errors import FetchError, FetchFailureCause, GistError, NotificationError
from peakguard.fetcher import PriceResult
from peakguard.main import run
from peakguard.notifier import ATHData, AlertData, FetchErrorData
from peakguard.storage import ClosingPrice


@pytest.fixture()
def sample_configs() -> list[TickerConfig]:
    return [
        TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        TickerConfig(ticker="MSFT", name="Microsoft", threshold=10.0),
    ]


@pytest.fixture(autouse=True)
def _set_gist_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure GIST_ID is always set for test runs."""
    monkeypatch.setenv("GIST_ID", "test-gist-id")


# AMZN rolling ATH=500.0 (2025-09-01), MSFT rolling ATH=400.0 (2025-09-01)
_HISTORY_CSV = (
    "ticker,date,price\n"
    "AMZN,2025-06-01,450.0\n"
    "AMZN,2025-09-01,500.0\n"
    "AMZN,2025-12-01,480.0\n"
    "AMZN,2026-03-05,490.0\n"
    "MSFT,2025-06-01,350.0\n"
    "MSFT,2025-09-01,400.0\n"
    "MSFT,2025-12-01,390.0\n"
    "MSFT,2026-03-05,395.0\n"
)

# AMZN ATH=600.0 at 2025-03-05, which expires when reference moves to 2026-03-06
_EXPIRY_HISTORY_CSV = (
    "ticker,date,price\n"
    "AMZN,2025-03-05,600.0\n"
    "AMZN,2025-09-01,500.0\n"
    "AMZN,2025-12-01,480.0\n"
    "AMZN,2026-03-05,490.0\n"
)


class TestRun:
    """Tests for the run() orchestration function with rolling window ATH."""

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_happy_path_no_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price drops but stays above threshold — no alerts sent."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=470.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_fetch_history.assert_not_called()
        mock_send_alert.assert_not_called()
        mock_send_ath_alert.assert_not_called()
        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_threshold_breach_sends_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price drops beyond threshold — MDD alert is sent."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        # AMZN: 440/500 = 12% drawdown (breaches 10%), MSFT: 385/400 = 3.75%
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=440.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_send_alert.assert_called_once()
        alert: AlertData = mock_send_alert.call_args[0][0]
        assert alert.ticker == "AMZN"
        assert alert.drawdown_pct == 12.0

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_new_ath_sends_ath_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price exceeds rolling ATH — ATH alert sent, no MDD alert."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=520.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_send_alert.assert_not_called()
        mock_send_ath_alert.assert_called_once()
        ath_data: ATHData = mock_send_ath_alert.call_args[0][0]
        assert ath_data.ticker == "AMZN"
        assert ath_data.new_peak == 520.0
        assert ath_data.peak_date == date(2026, 3, 6)

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_no_ath_change_no_ath_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """ATH stays the same — no ATH alert sent."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=470.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_send_ath_alert.assert_not_called()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_ath_drops_due_to_window_expiry(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """Old ATH expires from window — ATH drops, ATH alert sent."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        ]
        mock_read_gist.return_value = _EXPIRY_HISTORY_CSV
        # Today 2026-03-06: the 600.0 entry at 2025-03-05 falls outside the
        # 365-day window (cutoff becomes 2025-03-06), so ATH drops to 500.0
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)
        )

        run()

        mock_send_ath_alert.assert_called_once()
        ath_data: ATHData = mock_send_ath_alert.call_args[0][0]
        assert ath_data.ticker == "AMZN"
        assert ath_data.new_peak == 500.0

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_fetch_error_skips_ticker(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """One ticker fetch fails — others still processed."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            FetchError(ticker="AMZN", message="network error"),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_first_run_bootstrap(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """First run with empty gist — fetch_history called for all tickers."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.side_effect = GistError(
            message="File 'peak_prices.csv' not found"
        )
        mock_fetch_history.side_effect = [
            [
                ClosingPrice(ticker="AMZN", date=date(2025, 6, 1), price=450.0),
                ClosingPrice(ticker="AMZN", date=date(2025, 9, 1), price=500.0),
                ClosingPrice(ticker="AMZN", date=date(2026, 3, 5), price=490.0),
            ],
            [
                ClosingPrice(ticker="MSFT", date=date(2025, 6, 1), price=350.0),
                ClosingPrice(ticker="MSFT", date=date(2025, 9, 1), price=400.0),
                ClosingPrice(ticker="MSFT", date=date(2026, 3, 5), price=395.0),
            ],
        ]

        run()

        assert mock_fetch_history.call_count == 2
        mock_fetch_price.assert_not_called()
        # ATH alerts sent for both (initial ATH established)
        assert mock_send_ath_alert.call_count == 2
        mock_write_gist.assert_called_once()
        written_csv = mock_write_gist.call_args[1]["content"]
        assert "AMZN" in written_csv
        assert "MSFT" in written_csv

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_new_ticker_bootstrap(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """New ticker not in history — fetch_history for new, fetch_price for existing."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
            TickerConfig(ticker="TSLA", name="Tesla", threshold=10.0),
        ]
        mock_read_gist.return_value = _HISTORY_CSV  # has AMZN/MSFT, not TSLA
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)
        )
        mock_fetch_history.return_value = [
            ClosingPrice(ticker="TSLA", date=date(2025, 9, 1), price=250.0),
            ClosingPrice(ticker="TSLA", date=date(2026, 3, 5), price=300.0),
        ]

        run()

        mock_fetch_history.assert_called_once_with("TSLA")
        mock_fetch_price.assert_called_once_with("AMZN")
        # TSLA is new → ATH alert sent
        mock_send_ath_alert.assert_called_once()
        ath_data: ATHData = mock_send_ath_alert.call_args[0][0]
        assert ath_data.ticker == "TSLA"

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_notification_error_does_not_crash(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Telegram MDD alert failure — logged but does not crash."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=440.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]
        mock_send_alert.side_effect = NotificationError(message="Telegram down")

        run()

        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_ath_alert_error_does_not_crash(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """ATH alert send failure — logged but does not crash."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=520.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]
        mock_send_ath_alert.side_effect = NotificationError(message="Telegram down")

        run()

        mock_write_gist.assert_called_once()
        written_csv = mock_write_gist.call_args[1]["content"]
        assert "520.0" in written_csv

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_bootstrap_fetch_error_skips_ticker(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Bootstrap fetch_history fails for one ticker — others still processed."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.side_effect = GistError(message="not found")
        mock_fetch_history.side_effect = [
            FetchError(ticker="AMZN", message="timeout"),
            [
                ClosingPrice(ticker="MSFT", date=date(2025, 9, 1), price=400.0),
                ClosingPrice(ticker="MSFT", date=date(2026, 3, 5), price=395.0),
            ],
        ]

        run()

        mock_write_gist.assert_called_once()
        written_csv = mock_write_gist.call_args[1]["content"]
        assert "MSFT" in written_csv

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_history_saved_as_csv(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Updated history is saved to gist as CSV."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_write_gist.assert_called_once()
        call_kwargs = mock_write_gist.call_args[1]
        assert call_kwargs["filename"] == "peak_prices.csv"
        csv_content = call_kwargs["content"]
        assert csv_content.startswith("ticker,date,price\n")
        # New entries appended
        assert "2026-03-06" in csv_content


class TestRunFetchErrorNotification:
    """Tests for batch fetch-error notification in run()."""

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_no_fetch_errors_sends_empty_list(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """All fetches succeed → send_fetch_errors_alert called with empty list."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_send_fetch_errors.assert_called_once_with([])

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_fetch_errors_sends_batch_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Fetch fails → send_fetch_errors_alert called with error list."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            FetchError(
                ticker="AMZN",
                message="429 Too Many Requests",
                cause=FetchFailureCause.RATE_LIMIT,
            ),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        run()

        mock_send_fetch_errors.assert_called_once()
        errors = mock_send_fetch_errors.call_args[0][0]
        assert len(errors) == 1
        assert isinstance(errors[0], FetchErrorData)
        assert errors[0].ticker == "AMZN"
        assert errors[0].cause == FetchFailureCause.RATE_LIMIT

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_fetch_errors_alert")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_fetch_error_alert_failure_does_not_crash(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_send_fetch_errors: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """send_fetch_errors_alert raises NotificationError → run does not crash."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            FetchError(ticker="AMZN", message="error", cause=FetchFailureCause.UNKNOWN),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]
        mock_send_fetch_errors.side_effect = NotificationError(message="Telegram down")

        run()

        mock_write_gist.assert_called_once()
