"""Tests for main module — orchestration logic."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from peakguard.config import TickerConfig
from peakguard.errors import FetchError, GistError, NotificationError
from peakguard.fetcher import PriceResult
from peakguard.main import run
from peakguard.notifier import ATHData, AlertData


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


_PEAKS_JSON = (
    '{"AMZN": {"peak_price": 500.0, "peak_date": "2025-01-01"}, '
    '"MSFT": {"peak_price": 400.0, "peak_date": "2025-01-01"}}'
)


class TestRun:
    """Tests for the run() orchestration function."""

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_happy_path_no_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price drops but stays above threshold — no alert sent."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=480.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=390.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        mock_send_alert.assert_not_called()
        mock_send_ath_alert.assert_not_called()
        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_threshold_breach_sends_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price drops beyond threshold — alert is sent."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        # AMZN drops 12% (breaches 10% threshold), MSFT drops 5% (below threshold)
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=440.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=380.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        mock_send_alert.assert_called_once()
        alert: AlertData = mock_send_alert.call_args[0][0]
        assert alert.ticker == "AMZN"
        assert alert.drawdown_pct == 12.0
        mock_send_ath_alert.assert_not_called()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_new_ath_updates_peak(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price exceeds ATH — peak record is updated, no MDD alert."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=520.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=400.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        mock_send_alert.assert_not_called()
        # Verify the write_gist call contains the updated peak
        written_json = mock_write_gist.call_args[1]["content"]
        assert "520.0" in written_json

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_fetch_error_skips_ticker(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """One ticker fetch fails — others still processed."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            FetchError(ticker="AMZN", message="network error"),
            PriceResult(ticker="MSFT", price=380.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        # Should still complete without crashing
        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_first_run_empty_gist(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """First run with empty gist — initializes peaks from current prices."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.side_effect = GistError(
            message="File 'peak_prices.json' not found"
        )
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=500.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=400.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        mock_send_alert.assert_not_called()
        mock_write_gist.assert_called_once()
        written_json = mock_write_gist.call_args[1]["content"]
        assert "500.0" in written_json
        assert "400.0" in written_json

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_notification_error_does_not_crash(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Telegram send failure — logged but does not crash the run."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=440.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=380.0, fetched_at=date(2025, 6, 1)),
        ]
        mock_send_alert.side_effect = NotificationError(message="Telegram down")

        run()

        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_ath_update_sends_ath_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price exceeds ATH — send_ath_alert is called with correct ATHData."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=520.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=400.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        mock_send_ath_alert.assert_called_once()
        ath_data: ATHData = mock_send_ath_alert.call_args[0][0]
        assert ath_data.ticker == "AMZN"
        assert ath_data.new_peak == 520.0
        assert ath_data.peak_date == date(2025, 6, 1)
        mock_send_alert.assert_not_called()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_no_ath_update_does_not_send_ath_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price stays below ATH — send_ath_alert is not called."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=480.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=390.0, fetched_at=date(2025, 6, 1)),
        ]

        run()

        mock_send_ath_alert.assert_not_called()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_new_ticker_sends_ath_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """New ticker not in peaks — send_ath_alert is called."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="TSLA", name="Tesla", threshold=10.0),
        ]
        mock_read_gist.return_value = _PEAKS_JSON  # TSLA not in existing peaks
        mock_fetch_price.return_value = PriceResult(
            ticker="TSLA", price=300.0, fetched_at=date(2025, 6, 1)
        )

        run()

        mock_send_ath_alert.assert_called_once()
        ath_data: ATHData = mock_send_ath_alert.call_args[0][0]
        assert ath_data.ticker == "TSLA"
        assert ath_data.new_peak == 300.0
        assert ath_data.peak_date == date(2025, 6, 1)

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_ath_alert")
    @patch("peakguard.main.send_alert")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_portfolio")
    def test_ath_alert_error_does_not_crash(
        self,
        mock_load_portfolio: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_alert: MagicMock,
        mock_send_ath_alert: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """ATH alert send failure — logged but does not crash the run."""
        mock_load_portfolio.return_value = sample_configs
        mock_read_gist.return_value = _PEAKS_JSON
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=520.0, fetched_at=date(2025, 6, 1)),
            PriceResult(ticker="MSFT", price=400.0, fetched_at=date(2025, 6, 1)),
        ]
        mock_send_ath_alert.side_effect = NotificationError(message="Telegram down")

        run()

        mock_write_gist.assert_called_once()
        # Peak should still be updated despite alert failure
        written_json = mock_write_gist.call_args[1]["content"]
        assert "520.0" in written_json
