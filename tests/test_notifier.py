"""Tests for the notifier module — TickerSummary, format_daily_summary, send_daily_summary."""

import os
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from peakguard.errors import FetchFailureCause, NotificationError
from peakguard.notifier import (
    FetchErrorData,
    TickerSummary,
    format_daily_summary,
    send_daily_summary,
)

# ---------------------------------------------------------------------------
# FetchErrorData
# ---------------------------------------------------------------------------


class TestFetchErrorData:
    """Tests for the FetchErrorData dataclass."""

    def test_creation_with_valid_data(self) -> None:
        """Stores all fields correctly."""
        data = FetchErrorData(
            ticker="AAPL",
            cause=FetchFailureCause.RATE_LIMIT,
            reason="429 Too Many Requests",
        )
        assert data.ticker == "AAPL"
        assert data.cause == FetchFailureCause.RATE_LIMIT
        assert data.reason == "429 Too Many Requests"

    def test_is_frozen(self) -> None:
        """FetchErrorData instances are immutable."""
        data = FetchErrorData(
            ticker="AAPL",
            cause=FetchFailureCause.UNKNOWN,
            reason="error",
        )
        with pytest.raises(AttributeError):
            data.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        """Empty ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            FetchErrorData(
                ticker="",
                cause=FetchFailureCause.UNKNOWN,
                reason="error",
            )

    def test_rejects_whitespace_ticker(self) -> None:
        """Whitespace-only ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            FetchErrorData(
                ticker="   ",
                cause=FetchFailureCause.UNKNOWN,
                reason="error",
            )


# ---------------------------------------------------------------------------
# TickerSummary dataclass
# ---------------------------------------------------------------------------


class TestTickerSummary:
    """Tests for the TickerSummary dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Stores all fields correctly."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=213.21,
            ath=254.0,
            mdd_pct=16.06,
            days_since_ath=100,
            days_since_ath_limit=180,
            bounce_pct=27.43,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=True,
            ath_updated=False,
        )
        assert summary.ticker == "AMZN"
        assert summary.name == "Amazon"
        assert summary.current_price == 213.21
        assert summary.ath == 254.0
        assert summary.mdd_pct == 16.06
        assert summary.days_since_ath == 100
        assert summary.days_since_ath_limit == 180
        assert summary.bounce_pct == 27.43
        assert summary.mdd_alert is True
        assert summary.ath_stale_alert is False
        assert summary.bounce_alert is True
        assert summary.ath_updated is False

    def test_is_frozen(self) -> None:
        """TickerSummary instances are immutable."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=213.21,
            ath=254.0,
            mdd_pct=16.06,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
        )
        with pytest.raises(AttributeError):
            summary.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        """Empty ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            TickerSummary(
                ticker="",
                name="Amazon",
                current_price=213.21,
                ath=254.0,
                mdd_pct=None,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            )

    def test_rejects_whitespace_ticker(self) -> None:
        """Whitespace-only ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            TickerSummary(
                ticker="   ",
                name="Amazon",
                current_price=213.21,
                ath=254.0,
                mdd_pct=None,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            )

    def test_has_alert_true_when_mdd_alert(self) -> None:
        """has_alert is True when mdd_alert is True."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=213.21,
            ath=254.0,
            mdd_pct=16.06,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
        )
        assert summary.has_alert is True

    def test_has_alert_true_when_ath_stale_alert(self) -> None:
        """has_alert is True when ath_stale_alert is True."""
        summary = TickerSummary(
            ticker="META",
            name="Meta",
            current_price=644.86,
            ath=788.82,
            mdd_pct=18.25,
            days_since_ath=206,
            days_since_ath_limit=180,
            bounce_pct=None,
            mdd_alert=False,
            ath_stale_alert=True,
            bounce_alert=False,
            ath_updated=False,
        )
        assert summary.has_alert is True

    def test_has_alert_true_when_bounce_alert(self) -> None:
        """has_alert is True when bounce_alert is True."""
        summary = TickerSummary(
            ticker="NVDA",
            name="Nvidia",
            current_price=150.0,
            ath=200.0,
            mdd_pct=None,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=88.58,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=True,
            ath_updated=False,
        )
        assert summary.has_alert is True

    def test_has_alert_true_when_ath_updated(self) -> None:
        """has_alert is True when ath_updated is True."""
        summary = TickerSummary(
            ticker="GOOGL",
            name="Google",
            current_price=200.0,
            ath=200.0,
            mdd_pct=None,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=True,
        )
        assert summary.has_alert is True

    def test_has_alert_false_when_no_alerts(self) -> None:
        """has_alert is False when no alert flags are set."""
        summary = TickerSummary(
            ticker="GOOGL",
            name="Google",
            current_price=190.0,
            ath=200.0,
            mdd_pct=5.0,
            days_since_ath=10,
            days_since_ath_limit=180,
            bounce_pct=2.0,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
        )
        assert summary.has_alert is False

    def test_has_alert_true_when_multiple_alerts(self) -> None:
        """has_alert is True when multiple alert flags are set."""
        summary = TickerSummary(
            ticker="META",
            name="Meta",
            current_price=644.86,
            ath=788.82,
            mdd_pct=18.25,
            days_since_ath=206,
            days_since_ath_limit=180,
            bounce_pct=33.36,
            mdd_alert=True,
            ath_stale_alert=True,
            bounce_alert=True,
            ath_updated=False,
        )
        assert summary.has_alert is True

    def test_optional_fields_accept_none(self) -> None:
        """Optional fields (mdd_pct, days_since_ath, etc.) accept None."""
        summary = TickerSummary(
            ticker="NVDA",
            name="Nvidia",
            current_price=150.0,
            ath=150.0,
            mdd_pct=None,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
        )
        assert summary.mdd_pct is None
        assert summary.days_since_ath is None
        assert summary.days_since_ath_limit is None
        assert summary.bounce_pct is None


# ---------------------------------------------------------------------------
# format_daily_summary
# ---------------------------------------------------------------------------


class TestFormatDailySummary:
    """Tests for the format_daily_summary pure function."""

    def test_header_contains_date(self) -> None:
        """The summary header includes the report date."""
        result = format_daily_summary([], date(2026, 3, 7))
        assert "2026-03-07" in result

    def test_header_contains_title(self) -> None:
        """The summary header includes the PeakGuard title."""
        result = format_daily_summary([], date(2026, 3, 7))
        assert "PeakGuard" in result

    def test_no_alerts_day_shows_all_clear_message(self) -> None:
        """When no summaries have alerts, show an all-clear message."""
        summaries = [
            TickerSummary(
                ticker="GOOGL",
                name="Google",
                current_price=190.0,
                ath=200.0,
                mdd_pct=5.0,
                days_since_ath=10,
                days_since_ath_limit=180,
                bounce_pct=2.0,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "이상 없음" in result

    def test_empty_summaries_shows_all_clear(self) -> None:
        """Empty list of summaries also shows all-clear."""
        result = format_daily_summary([], date(2026, 3, 7))
        assert "이상 없음" in result

    def test_mdd_alert_ticker_shows_mdd_section(self) -> None:
        """Ticker with MDD alert shows drawdown info."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=213.21,
                ath=254.0,
                mdd_pct=16.06,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "AMZN" in result
        assert "Amazon" in result
        assert "MDD" in result or "📉" in result
        assert "$213.21" in result
        assert "$254.00" in result
        assert "-16.06%" in result

    def test_bounce_alert_shows_bounce_info(self) -> None:
        """Ticker with bounce alert shows bounce percentage."""
        summaries = [
            TickerSummary(
                ticker="NVDA",
                name="Nvidia",
                current_price=150.0,
                ath=200.0,
                mdd_pct=25.0,
                days_since_ath=100,
                days_since_ath_limit=180,
                bounce_pct=88.58,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=True,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "NVDA" in result
        assert "+88.58%" in result
        assert "반등" in result or "📈" in result

    def test_ath_stale_alert_shows_days_info(self) -> None:
        """Ticker with stale ATH shows days elapsed and limit."""
        summaries = [
            TickerSummary(
                ticker="META",
                name="Meta",
                current_price=644.86,
                ath=788.82,
                mdd_pct=18.25,
                days_since_ath=206,
                days_since_ath_limit=180,
                bounce_pct=None,
                mdd_alert=True,
                ath_stale_alert=True,
                bounce_alert=False,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "META" in result
        assert "206" in result
        assert "180" in result

    def test_ath_updated_shows_new_ath(self) -> None:
        """Ticker with ATH update shows the new high marker."""
        summaries = [
            TickerSummary(
                ticker="GOOGL",
                name="Google",
                current_price=210.0,
                ath=210.0,
                mdd_pct=None,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=True,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "GOOGL" in result
        assert "ATH" in result

    def test_combined_mdd_and_bounce_alert(self) -> None:
        """Ticker with both MDD and bounce shows both status labels."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=213.21,
                ath=254.0,
                mdd_pct=16.06,
                days_since_ath=100,
                days_since_ath_limit=180,
                bounce_pct=27.43,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=True,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "📉" in result
        assert "📈" in result
        assert "-16.06%" in result
        assert "+27.43%" in result

    def test_triple_alert_mdd_stale_bounce(self) -> None:
        """Ticker with MDD, stale ATH, and bounce shows all three."""
        summaries = [
            TickerSummary(
                ticker="META",
                name="Meta",
                current_price=644.86,
                ath=788.82,
                mdd_pct=18.25,
                days_since_ath=206,
                days_since_ath_limit=180,
                bounce_pct=33.36,
                mdd_alert=True,
                ath_stale_alert=True,
                bounce_alert=True,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "📉" in result
        assert "⏸" in result
        assert "📈" in result
        assert "-18.25%" in result
        assert "206" in result
        assert "+33.36%" in result

    def test_multiple_tickers_each_has_section(self) -> None:
        """Multiple alert tickers each get their own section."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=213.21,
                ath=254.0,
                mdd_pct=16.06,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            ),
            TickerSummary(
                ticker="NVDA",
                name="Nvidia",
                current_price=150.0,
                ath=200.0,
                mdd_pct=None,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=88.58,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=True,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "AMZN" in result
        assert "NVDA" in result

    def test_non_alert_tickers_excluded(self) -> None:
        """Tickers with no alerts are not in the output body."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=213.21,
                ath=254.0,
                mdd_pct=16.06,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            ),
            TickerSummary(
                ticker="GOOGL",
                name="Google",
                current_price=190.0,
                ath=200.0,
                mdd_pct=5.0,
                days_since_ath=10,
                days_since_ath_limit=180,
                bounce_pct=1.0,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "AMZN" in result
        # GOOGL section should not appear as it has no alerts
        # But GOOGL might appear in a summary count — check no section header
        lines = result.split("\n")
        googl_section_lines = [
            line for line in lines if "GOOGL" in line and "Google" in line
        ]
        assert len(googl_section_lines) == 0

    def test_fetch_errors_section_appears(self) -> None:
        """Fetch errors are included in the summary when provided."""
        from peakguard.notifier import FetchErrorData

        errors = [
            FetchErrorData(
                ticker="TSLA",
                cause=FetchFailureCause.RATE_LIMIT,
                reason="429 Too Many Requests",
            ),
        ]
        result = format_daily_summary([], date(2026, 3, 7), fetch_errors=errors)
        assert "TSLA" in result
        assert "429" in result or "Rate Limit" in result


# ---------------------------------------------------------------------------
# send_daily_summary
# ---------------------------------------------------------------------------


class TestSendDailySummary:
    """Tests for the send_daily_summary function."""

    @pytest.fixture(autouse=True)
    def _set_env(self, mocker) -> None:
        """Provide valid Telegram env vars for every test by default."""
        mocker.patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "fake-token-123",
                "TELEGRAM_CHAT_ID": "99999",
            },
        )

    def _make_summary(self, ticker: str = "AMZN") -> TickerSummary:
        """Helper to create a valid TickerSummary for testing."""
        return TickerSummary(
            ticker=ticker,
            name="Amazon",
            current_price=213.21,
            ath=254.0,
            mdd_pct=16.06,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
        )

    def test_sends_post_request_on_success(self, mocker) -> None:
        """Happy path: sends a single Telegram message."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_daily_summary([self._make_summary()], date(2026, 3, 7))

        mock_post.assert_called_once()

    def test_message_contains_formatted_summary(self, mocker) -> None:
        """Posted message contains the formatted daily summary text."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_daily_summary([self._make_summary()], date(2026, 3, 7))

        payload = mock_post.call_args[1]["json"]
        text = payload["text"]
        assert "PeakGuard" in text
        assert "2026-03-07" in text
        assert "AMZN" in text

    def test_uses_correct_token_and_chat_id(self, mocker) -> None:
        """URL contains the bot token and payload contains the chat_id."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_daily_summary([self._make_summary()], date(2026, 3, 7))

        url = mock_post.call_args[0][0]
        assert "fake-token-123" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "99999"

    def test_raises_value_error_when_token_missing(self, mocker) -> None:
        """Missing TELEGRAM_BOT_TOKEN → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}, clear=False)

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            send_daily_summary([self._make_summary()], date(2026, 3, 7))

    def test_raises_value_error_when_chat_id_missing(self, mocker) -> None:
        """Missing TELEGRAM_CHAT_ID → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": ""}, clear=False)

        with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID"):
            send_daily_summary([self._make_summary()], date(2026, 3, 7))

    def test_raises_notification_error_on_http_error(self, mocker) -> None:
        """Non-2xx response from Telegram API → NotificationError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "400 Bad Request"
        )
        mocker.patch("peakguard.notifier.requests.post", return_value=mock_response)

        with pytest.raises(NotificationError, match="400"):
            send_daily_summary([self._make_summary()], date(2026, 3, 7))

    def test_wraps_network_error_in_notification_error(self, mocker) -> None:
        """Network failure is wrapped in NotificationError."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(NotificationError, match="network down"):
            send_daily_summary([self._make_summary()], date(2026, 3, 7))

    def test_sends_all_clear_when_no_alerts(self, mocker) -> None:
        """No alert summaries → sends a message with all-clear text."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_daily_summary([], date(2026, 3, 7))

        mock_post.assert_called_once()
        text = mock_post.call_args[1]["json"]["text"]
        assert "이상 없음" in text

    def test_includes_fetch_errors_in_message(self, mocker) -> None:
        """Fetch errors are appended to the summary message."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        errors = [
            FetchErrorData(
                ticker="TSLA",
                cause=FetchFailureCause.RATE_LIMIT,
                reason="429 Too Many Requests",
            ),
        ]
        send_daily_summary([], date(2026, 3, 7), fetch_errors=errors)

        text = mock_post.call_args[1]["json"]["text"]
        assert "TSLA" in text
