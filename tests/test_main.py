"""Tests for main module — consolidated daily summary orchestration."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from peakguard.config import AlertThresholds, AssetType, TickerConfig
from peakguard.errors import (
    FetchError,
    FetchFailureCause,
    GistError,
    GistFailureCause,
    NotificationError,
)
from peakguard.fetcher import PriceResult
from peakguard.mdd_calc import ReviewLevel
from peakguard.notifier import (
    FetchErrorData,
    HealthStatus,
    RunHealth,
    TickerSummary,
)
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


# History where AMZN ATH=500.0 at 2025-06-01 (>180 days before 2026-03-06)
# and prices clearly decline, making Z-score and bounce metrics calculable.
_METRICS_HISTORY_CSV = (
    "ticker,date,price\n"
    "AMZN,2025-06-01,500.0\n"
    "AMZN,2025-07-01,490.0\n"
    "AMZN,2025-08-01,480.0\n"
    "AMZN,2025-09-01,470.0\n"
    "AMZN,2025-10-01,420.0\n"
    "AMZN,2025-11-01,410.0\n"
    "AMZN,2025-12-01,400.0\n"
    "AMZN,2026-01-01,390.0\n"
    "AMZN,2026-02-01,380.0\n"
    "AMZN,2026-03-05,385.0\n"
)


class TestRun:
    """Tests for the run() orchestration with consolidated daily summary."""

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_happy_path_no_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price drops but stays above threshold — no alert flags set."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=470.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        mock_fetch_history.assert_not_called()
        mock_send_summary.assert_called_once()
        summaries = mock_send_summary.call_args[0][0]
        assert len(summaries) == 2
        for s in summaries:
            assert isinstance(s, TickerSummary)
            assert s.mdd_alert is False
            assert s.ath_updated is False
        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_threshold_breach_sets_mdd_alert(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price drops beyond threshold — TickerSummary has mdd_alert=True."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        # AMZN: 440/500 = 12% drawdown (breaches 10%), MSFT: 385/400 = 3.75%
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=440.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        mock_send_summary.assert_called_once()
        summaries = mock_send_summary.call_args[0][0]
        amzn = next(s for s in summaries if s.ticker == "AMZN")
        msft = next(s for s in summaries if s.ticker == "MSFT")
        assert amzn.mdd_alert is True
        assert amzn.mdd_pct == 12.0
        assert amzn.review_level == ReviewLevel.WATCH
        assert msft.mdd_alert is False

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_new_ath_sets_ath_updated(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Price exceeds rolling ATH — TickerSummary has ath_updated=True."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=520.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        mock_send_summary.assert_called_once()
        summaries = mock_send_summary.call_args[0][0]
        amzn = next(s for s in summaries if s.ticker == "AMZN")
        assert amzn.ath_updated is True
        assert amzn.ath == 520.0
        # Price at/above ATH → no drawdown
        assert amzn.mdd_pct is None
        assert amzn.mdd_alert is False

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_no_ath_change_ath_updated_false(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """ATH stays the same — ath_updated is False."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=470.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        for s in summaries:
            assert s.ath_updated is False

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_ath_drops_due_to_window_expiry(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """Old ATH expires from window — ATH drops, ath_updated stays False
        (ATH dropped, not a new high)."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _EXPIRY_HISTORY_CSV
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)
        )

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        amzn = summaries[0]
        assert amzn.ath == 500.0
        # ATH dropped from 600 to 500 — NOT a new high
        assert amzn.ath_updated is False

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_fetch_error_skips_ticker(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """One ticker fetch fails — not included in summaries, error passed."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            FetchError(ticker="AMZN", message="network error"),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        mock_send_summary.assert_called_once()
        summaries = mock_send_summary.call_args[0][0]
        assert len(summaries) == 1
        assert summaries[0].ticker == "MSFT"
        # Fetch errors passed via keyword argument
        call_kwargs = mock_send_summary.call_args[1]
        errors = call_kwargs.get("fetch_errors", [])
        assert len(errors) == 1
        assert errors[0].ticker == "AMZN"
        health = call_kwargs["data_health"]
        assert health.fetch_status == HealthStatus.PARTIAL
        assert health.fetch_succeeded == 1
        assert health.fetch_failed == 1
        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_first_run_bootstrap(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """First run with empty gist — fetch_history called, summaries built."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.side_effect = GistError(
            message="File 'peak_prices.csv' not found",
            cause=GistFailureCause.MISSING_FILE,
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

        from peakguard.main import run

        run()

        assert mock_fetch_history.call_count == 2
        mock_fetch_price.assert_not_called()
        mock_send_summary.assert_called_once()
        summaries = mock_send_summary.call_args[0][0]
        assert len(summaries) == 2
        tickers = {s.ticker for s in summaries}
        assert tickers == {"AMZN", "MSFT"}
        mock_write_gist.assert_called_once()
        written_csv = mock_write_gist.call_args[1]["content"]
        assert "AMZN" in written_csv
        assert "MSFT" in written_csv

    @pytest.mark.parametrize(
        "cause",
        [
            GistFailureCause.AUTHENTICATION,
            GistFailureCause.RATE_LIMIT,
            GistFailureCause.NETWORK,
            GistFailureCause.MALFORMED_RESPONSE,
            GistFailureCause.UNKNOWN,
        ],
    )
    def test_fatal_gist_read_failure_stops_before_evaluation_or_write(
        self,
        mocker,
        sample_configs: list[TickerConfig],
        cause: GistFailureCause,
    ) -> None:
        """Only a missing history file may enter the bootstrap pipeline."""
        mocker.patch("peakguard.main.load_portfolio", return_value=sample_configs)
        mocker.patch("peakguard.main.load_alert_thresholds")
        mocker.patch(
            "peakguard.main.read_gist",
            side_effect=GistError(message="history unavailable", cause=cause),
        )
        mock_fetch_history = mocker.patch("peakguard.main.fetch_history")
        mock_fetch_price = mocker.patch("peakguard.main.fetch_price")
        mock_send_summary = mocker.patch("peakguard.main.send_daily_summary")
        mock_write_gist = mocker.patch("peakguard.main.write_gist")

        from peakguard.main import run

        with pytest.raises(GistError) as exc_info:
            run()

        assert exc_info.value.cause == cause
        mock_fetch_history.assert_not_called()
        mock_fetch_price.assert_not_called()
        mock_send_summary.assert_called_once()
        summaries, _report_date = mock_send_summary.call_args.args
        health = mock_send_summary.call_args.kwargs["data_health"]
        assert summaries == []
        assert health == RunHealth(
            fetch_succeeded=0,
            fetch_failed=0,
            gist_read=HealthStatus.FAILED,
            gist_write=HealthStatus.NOT_ATTEMPTED,
            signals_evaluated=False,
            history_modified=False,
        )
        mock_write_gist.assert_not_called()

    def test_malformed_csv_stops_before_evaluation_or_write(
        self, mocker, sample_configs: list[TickerConfig]
    ) -> None:
        """Invalid persisted CSV is fatal and cannot be replaced automatically."""
        mocker.patch("peakguard.main.load_portfolio", return_value=sample_configs)
        mocker.patch("peakguard.main.load_alert_thresholds")
        mocker.patch("peakguard.main.read_gist", return_value="wrong,header\n")
        mock_fetch_history = mocker.patch("peakguard.main.fetch_history")
        mock_fetch_price = mocker.patch("peakguard.main.fetch_price")
        mock_send_summary = mocker.patch("peakguard.main.send_daily_summary")
        mock_write_gist = mocker.patch("peakguard.main.write_gist")

        from peakguard.main import run

        with pytest.raises(GistError) as exc_info:
            run()

        assert exc_info.value.cause == GistFailureCause.MALFORMED_HISTORY
        mock_fetch_history.assert_not_called()
        mock_fetch_price.assert_not_called()
        mock_send_summary.assert_called_once()
        health = mock_send_summary.call_args.kwargs["data_health"]
        assert health.gist_read == HealthStatus.FAILED
        assert health.signals_evaluated is False
        assert health.history_modified is False
        mock_write_gist.assert_not_called()

    def test_gist_write_failure_is_reported_then_propagated(
        self, mocker, sample_configs: list[TickerConfig]
    ) -> None:
        """A failed write produces health reporting and still fails the run."""
        mocker.patch("peakguard.main.load_portfolio", return_value=sample_configs)
        mocker.patch(
            "peakguard.main.load_alert_thresholds",
            return_value=AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=3.0,
            ),
        )
        mocker.patch("peakguard.main.read_gist", return_value=_HISTORY_CSV)
        mocker.patch(
            "peakguard.main.fetch_price",
            side_effect=[
                PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
                PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
            ],
        )
        events: list[str] = []
        write_error = GistError(
            message="write unavailable", cause=GistFailureCause.NETWORK
        )

        def fail_write(**_kwargs) -> None:
            events.append("write")
            raise write_error

        mock_write_gist = mocker.patch(
            "peakguard.main.write_gist",
            side_effect=fail_write,
        )
        mock_send_summary = mocker.patch(
            "peakguard.main.send_daily_summary",
            side_effect=lambda *_args, **_kwargs: events.append("notify"),
        )

        from peakguard.main import run

        with pytest.raises(GistError) as exc_info:
            run()

        assert exc_info.value is write_error
        assert events == ["write", "notify"]
        mock_write_gist.assert_called_once()
        health = mock_send_summary.call_args.kwargs["data_health"]
        assert health.gist_read == HealthStatus.SUCCEEDED
        assert health.gist_write == HealthStatus.FAILED
        assert health.signals_evaluated is True
        assert health.history_modified is False

    def test_healthy_run_reports_complete_data_health(
        self, mocker, sample_configs: list[TickerConfig]
    ) -> None:
        """A fully successful run reports fetch, read, write, and signal health."""
        mocker.patch("peakguard.main.load_portfolio", return_value=sample_configs)
        mocker.patch(
            "peakguard.main.load_alert_thresholds",
            return_value=AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=3.0,
            ),
        )
        mocker.patch("peakguard.main.read_gist", return_value=_HISTORY_CSV)
        mocker.patch(
            "peakguard.main.fetch_price",
            side_effect=[
                PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
                PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
            ],
        )
        events: list[str] = []
        mocker.patch(
            "peakguard.main.write_gist",
            side_effect=lambda **_kwargs: events.append("write"),
        )
        mock_send_summary = mocker.patch(
            "peakguard.main.send_daily_summary",
            side_effect=lambda *_args, **_kwargs: events.append("notify"),
        )

        from peakguard.main import run

        run()

        assert events == ["write", "notify"]
        assert mock_send_summary.call_args.kwargs["data_health"] == RunHealth(
            fetch_succeeded=2,
            fetch_failed=0,
            gist_read=HealthStatus.SUCCEEDED,
            gist_write=HealthStatus.SUCCEEDED,
            signals_evaluated=True,
            history_modified=True,
        )

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_new_ticker_bootstrap(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """New ticker not in history — fetch_history for new,
        fetch_price for existing."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
            TickerConfig(ticker="TSLA", name="Tesla", threshold=10.0),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)
        )
        mock_fetch_history.return_value = [
            ClosingPrice(ticker="TSLA", date=date(2025, 9, 1), price=250.0),
            ClosingPrice(ticker="TSLA", date=date(2026, 3, 5), price=300.0),
        ]

        from peakguard.main import run

        run()

        mock_fetch_history.assert_called_once_with("TSLA")
        mock_fetch_price.assert_called_once_with("AMZN")
        mock_send_summary.assert_called_once()
        summaries = mock_send_summary.call_args[0][0]
        tickers = {s.ticker for s in summaries}
        assert tickers == {"AMZN", "TSLA"}

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_notification_error_does_not_crash(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """send_daily_summary failure — logged but does not crash."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=440.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=385.0, fetched_at=date(2026, 3, 6)),
        ]
        mock_send_summary.side_effect = NotificationError(message="Telegram down")

        from peakguard.main import run

        run()

        mock_write_gist.assert_called_once()

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_bootstrap_fetch_error_skips_ticker(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Bootstrap fetch_history fails for one ticker — others still processed."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.side_effect = GistError(
            message="not found", cause=GistFailureCause.MISSING_FILE
        )
        mock_fetch_history.side_effect = [
            FetchError(ticker="AMZN", message="timeout"),
            [
                ClosingPrice(ticker="MSFT", date=date(2025, 9, 1), price=400.0),
                ClosingPrice(ticker="MSFT", date=date(2026, 3, 5), price=395.0),
            ],
        ]

        from peakguard.main import run

        run()

        mock_write_gist.assert_called_once()
        written_csv = mock_write_gist.call_args[1]["content"]
        assert "MSFT" in written_csv
        summaries = mock_send_summary.call_args[0][0]
        assert len(summaries) == 1
        assert summaries[0].ticker == "MSFT"

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_history_saved_as_csv(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Updated history is saved to gist as CSV."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        mock_write_gist.assert_called_once()
        call_kwargs = mock_write_gist.call_args[1]
        assert call_kwargs["filename"] == "peak_prices.csv"
        csv_content = call_kwargs["content"]
        assert csv_content.startswith("ticker,date,price\n")
        assert "2026-03-06" in csv_content

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_report_date_passed_to_send_daily_summary(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """report_date is passed as the reference date from fetched prices."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        report_date = mock_send_summary.call_args[0][1]
        assert report_date == date(2026, 3, 6)

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_summary_contains_name_from_config(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """TickerSummary.name comes from TickerConfig.name."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        amzn = next(s for s in summaries if s.ticker == "AMZN")
        msft = next(s for s in summaries if s.ticker == "MSFT")
        assert amzn.name == "Amazon"
        assert msft.name == "Microsoft"

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_price_at_ath_has_no_drawdown_metrics(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """Price at ATH → mdd_pct, days_since_ath, bounce_pct are None."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=500.0, fetched_at=date(2026, 3, 6)
        )

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        amzn = summaries[0]
        assert amzn.mdd_pct is None
        assert amzn.days_since_ath is None
        assert amzn.bounce_pct is None
        assert amzn.mdd_alert is False
        assert amzn.ath_stale_alert is False
        assert amzn.bounce_alert is False


class TestRunFetchErrorNotification:
    """Tests for fetch error handling in consolidated summary."""

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_no_fetch_errors_passes_empty_list(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """All fetches succeed → fetch_errors is empty list."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            PriceResult(ticker="AMZN", price=490.0, fetched_at=date(2026, 3, 6)),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        call_kwargs = mock_send_summary.call_args[1]
        assert call_kwargs.get("fetch_errors") == []

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_fetch_errors_passed_to_summary(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
        sample_configs: list[TickerConfig],
    ) -> None:
        """Fetch fails → error passed via fetch_errors kwarg."""
        mock_load_portfolio.return_value = sample_configs
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _HISTORY_CSV
        mock_fetch_price.side_effect = [
            FetchError(
                ticker="AMZN",
                message="429 Too Many Requests",
                cause=FetchFailureCause.RATE_LIMIT,
            ),
            PriceResult(ticker="MSFT", price=395.0, fetched_at=date(2026, 3, 6)),
        ]

        from peakguard.main import run

        run()

        call_kwargs = mock_send_summary.call_args[1]
        errors = call_kwargs["fetch_errors"]
        assert len(errors) == 1
        assert isinstance(errors[0], FetchErrorData)
        assert errors[0].ticker == "AMZN"
        assert errors[0].cause == FetchFailureCause.RATE_LIMIT


class TestRunMetricAlerts:
    """Tests for metric alert flags in TickerSummary."""

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_days_since_ath_alert_flag_set(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """ATH is >180 days old → ath_stale_alert is True."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _METRICS_HISTORY_CSV
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=390.0, fetched_at=date(2026, 3, 6)
        )

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        amzn = summaries[0]
        assert amzn.ath_stale_alert is True
        assert amzn.days_since_ath is not None
        assert amzn.days_since_ath > 180

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_bounce_alert_flag_set(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """Bounce from low exceeds min_pct → bounce_alert is True."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _METRICS_HISTORY_CSV
        # Low in history is 380.0; price 400.0 → bounce ≈ 5.26%
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=400.0, fetched_at=date(2026, 3, 6)
        )

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        amzn = summaries[0]
        assert amzn.bounce_alert is True
        assert amzn.bounce_pct is not None
        assert amzn.bounce_pct >= 3.0

    @pytest.mark.parametrize(
        ("zscore", "expected_alert"),
        [(-2.0001, True), (-2.0, True), (-1.9999, False)],
    )
    def test_zscore_threshold_is_inclusive(
        self,
        mocker,
        zscore: float,
        expected_alert: bool,
    ) -> None:
        """Z-score alerts activate at or below the configured threshold."""
        mocker.patch(
            "peakguard.main.load_portfolio",
            return_value=[
                TickerConfig(ticker="AMZN", name="Amazon", threshold=50.0),
            ],
        )
        mocker.patch(
            "peakguard.main.load_alert_thresholds",
            return_value=AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=50.0,
            ),
        )
        mocker.patch("peakguard.main.read_gist", return_value=_METRICS_HISTORY_CSV)
        mocker.patch(
            "peakguard.main.fetch_price",
            return_value=PriceResult(
                ticker="AMZN", price=390.0, fetched_at=date(2026, 3, 6)
            ),
        )
        mocker.patch("peakguard.main.calculate_price_zscore", return_value=zscore)
        mocker.patch("peakguard.main.write_gist")
        mock_send_summary = mocker.patch("peakguard.main.send_daily_summary")

        from peakguard.main import run

        run()

        summary = mock_send_summary.call_args.args[0][0]
        assert summary.zscore == zscore
        assert summary.zscore_alert is expected_alert
        expected_level = ReviewLevel.ATTRACTIVE if expected_alert else ReviewLevel.NONE
        assert summary.review_level == expected_level

    def test_mdd_and_zscore_breach_is_deep_discount(self, mocker) -> None:
        """Joint drawdown and statistical weakness produce the strongest level."""
        mocker.patch(
            "peakguard.main.load_portfolio",
            return_value=[
                TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
            ],
        )
        mocker.patch(
            "peakguard.main.load_alert_thresholds",
            return_value=AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=50.0,
            ),
        )
        mocker.patch("peakguard.main.read_gist", return_value=_METRICS_HISTORY_CSV)
        mocker.patch(
            "peakguard.main.fetch_price",
            return_value=PriceResult(
                ticker="AMZN", price=390.0, fetched_at=date(2026, 3, 6)
            ),
        )
        mocker.patch("peakguard.main.calculate_price_zscore", return_value=-2.1)
        mocker.patch("peakguard.main.write_gist")
        mock_send_summary = mocker.patch("peakguard.main.send_daily_summary")

        from peakguard.main import run

        run()

        summary = mock_send_summary.call_args.args[0][0]
        assert summary.mdd_alert is True
        assert summary.zscore_alert is True
        assert summary.review_level == ReviewLevel.DEEP_DISCOUNT

    @pytest.mark.parametrize(
        "closing_prices",
        [
            [ClosingPrice(ticker="AMZN", date=date(2026, 3, 6), price=100.0)],
            [
                ClosingPrice(ticker="AMZN", date=date(2026, 3, 5), price=100.0),
                ClosingPrice(ticker="AMZN", date=date(2026, 3, 6), price=100.0),
            ],
        ],
    )
    def test_uncalculable_zscore_is_safe_none(
        self, mocker, closing_prices: list[ClosingPrice]
    ) -> None:
        """Insufficient or zero-variance history does not abort the run."""
        mocker.patch(
            "peakguard.main.load_portfolio",
            return_value=[
                TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
            ],
        )
        mocker.patch(
            "peakguard.main.load_alert_thresholds",
            return_value=AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=3.0,
            ),
        )
        mocker.patch(
            "peakguard.main.read_gist",
            side_effect=GistError(
                message="missing", cause=GistFailureCause.MISSING_FILE
            ),
        )
        mocker.patch("peakguard.main.fetch_history", return_value=closing_prices)
        mocker.patch("peakguard.main.write_gist")
        mock_send_summary = mocker.patch("peakguard.main.send_daily_summary")

        from peakguard.main import run

        run()

        summary = mock_send_summary.call_args.args[0][0]
        assert summary.zscore is None
        assert summary.zscore_alert is False
        assert summary.review_level == ReviewLevel.NONE

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_no_metric_alerts_when_price_at_ath(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """Price at ATH → no metric alert flags set."""
        mock_load_portfolio.return_value = [
            TickerConfig(ticker="AMZN", name="Amazon", threshold=10.0),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = _METRICS_HISTORY_CSV
        mock_fetch_price.return_value = PriceResult(
            ticker="AMZN", price=510.0, fetched_at=date(2026, 3, 6)
        )

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        amzn = summaries[0]
        assert amzn.mdd_alert is False
        assert amzn.ath_stale_alert is False
        assert amzn.bounce_alert is False

    @patch("peakguard.main.write_gist")
    @patch("peakguard.main.send_daily_summary")
    @patch("peakguard.main.fetch_price")
    @patch("peakguard.main.fetch_history")
    @patch("peakguard.main.read_gist")
    @patch("peakguard.main.load_alert_thresholds")
    @patch("peakguard.main.load_portfolio")
    def test_krw_ticker_currency_propagated(
        self,
        mock_load_portfolio: MagicMock,
        mock_load_thresholds: MagicMock,
        mock_read_gist: MagicMock,
        mock_fetch_history: MagicMock,
        mock_fetch_price: MagicMock,
        mock_send_summary: MagicMock,
        mock_write_gist: MagicMock,
    ) -> None:
        """KRW currency from TickerConfig is propagated to TickerSummary."""
        mock_load_portfolio.return_value = [
            TickerConfig(
                ticker="360750.KS",
                name="TIGER 미국S&P500",
                threshold=15.0,
                currency="KRW",
                asset_type=AssetType.CORE_ETF,
                portfolio_group="US Equity",
                proxy_for="SPY",
            ),
        ]
        mock_load_thresholds.return_value = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        mock_read_gist.return_value = (
            "ticker,date,price\n"
            "360750.KS,2025-06-01,14000.0\n"
            "360750.KS,2025-09-01,18000.0\n"
            "360750.KS,2026-03-05,16500.0\n"
        )
        mock_fetch_price.return_value = PriceResult(
            ticker="360750.KS", price=15280.0, fetched_at=date(2026, 3, 6)
        )

        from peakguard.main import run

        run()

        summaries = mock_send_summary.call_args[0][0]
        tiger = summaries[0]
        assert tiger.ticker == "360750.KS"
        assert tiger.currency == "KRW"
        assert tiger.asset_type is AssetType.CORE_ETF
        assert tiger.thesis_required is False
