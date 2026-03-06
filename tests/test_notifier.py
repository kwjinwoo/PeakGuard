"""Tests for the notifier module — AlertData, send_alert, send_alerts, ATHData, and send_ath_alert."""

import os
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from peakguard.errors import FetchFailureCause, NotificationError
from peakguard.notifier import (
    ATHData,
    AlertData,
    BounceAlertData,
    DaysSinceATHAlertData,
    FetchErrorData,
    ZScoreAlertData,
    send_alert,
    send_alerts,
    send_ath_alert,
    send_bounce_alert,
    send_days_since_ath_alert,
    send_fetch_errors_alert,
    send_zscore_alert,
)


class TestAlertData:
    """Tests for the AlertData dataclass."""

    def test_creation_with_valid_data(self) -> None:
        """Stores all fields correctly."""
        alert = AlertData(
            ticker="AAPL",
            current_price=150.0,
            peak_price=200.0,
            drawdown_pct=25.0,
        )
        assert alert.ticker == "AAPL"
        assert alert.current_price == 150.0
        assert alert.peak_price == 200.0
        assert alert.drawdown_pct == 25.0

    def test_is_frozen(self) -> None:
        """AlertData instances are immutable."""
        alert = AlertData(
            ticker="AAPL",
            current_price=150.0,
            peak_price=200.0,
            drawdown_pct=25.0,
        )
        with pytest.raises(AttributeError):
            alert.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        """Empty ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            AlertData(
                ticker="",
                current_price=150.0,
                peak_price=200.0,
                drawdown_pct=25.0,
            )

    def test_rejects_whitespace_ticker(self) -> None:
        """Whitespace-only ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            AlertData(
                ticker="   ",
                current_price=150.0,
                peak_price=200.0,
                drawdown_pct=25.0,
            )

    def test_rejects_negative_drawdown(self) -> None:
        """Negative drawdown_pct is invalid → ValueError."""
        with pytest.raises(ValueError, match="drawdown_pct"):
            AlertData(
                ticker="AAPL",
                current_price=150.0,
                peak_price=200.0,
                drawdown_pct=-5.0,
            )

    def test_rejects_drawdown_over_100(self) -> None:
        """drawdown_pct over 100 is invalid → ValueError."""
        with pytest.raises(ValueError, match="drawdown_pct"):
            AlertData(
                ticker="AAPL",
                current_price=150.0,
                peak_price=200.0,
                drawdown_pct=105.0,
            )

    def test_accepts_zero_drawdown(self) -> None:
        """drawdown_pct of 0 is valid (price at ATH)."""
        alert = AlertData(
            ticker="AAPL",
            current_price=200.0,
            peak_price=200.0,
            drawdown_pct=0.0,
        )
        assert alert.drawdown_pct == 0.0

    def test_accepts_100_drawdown(self) -> None:
        """drawdown_pct of 100 is valid (total loss)."""
        alert = AlertData(
            ticker="AAPL",
            current_price=0.01,
            peak_price=200.0,
            drawdown_pct=100.0,
        )
        assert alert.drawdown_pct == 100.0


class TestSendAlert:
    """Tests for the send_alert function."""

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

    def _make_alert(self) -> AlertData:
        """Helper to create a valid AlertData for testing."""
        return AlertData(
            ticker="AAPL",
            current_price=150.0,
            peak_price=200.0,
            drawdown_pct=25.0,
        )

    def test_sends_post_request_on_success(self, mocker) -> None:
        """Happy path: sends Telegram message and returns without error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_alert(self._make_alert())

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://api.telegram.org/bot" in call_args[0][0]
        assert "sendMessage" in call_args[0][0]

    def test_message_contains_alert_details(self, mocker) -> None:
        """Posted message text includes ticker, prices, and drawdown."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_alert(self._make_alert())

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[1]
        text = payload["text"]
        assert "AAPL" in text
        assert "150.0" in text or "150" in text
        assert "200.0" in text or "200" in text
        assert "25.0" in text or "25" in text

    def test_uses_correct_token_and_chat_id(self, mocker) -> None:
        """URL contains the bot token and payload contains the chat_id."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_alert(self._make_alert())

        url = mock_post.call_args[0][0]
        assert "fake-token-123" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "99999"

    def test_raises_value_error_when_token_missing(self, mocker) -> None:
        """Missing TELEGRAM_BOT_TOKEN is a programmer error → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}, clear=False)

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            send_alert(self._make_alert())

    def test_raises_value_error_when_chat_id_missing(self, mocker) -> None:
        """Missing TELEGRAM_CHAT_ID is a programmer error → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": ""}, clear=False)

        with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID"):
            send_alert(self._make_alert())

    def test_raises_value_error_when_token_not_set(self, mocker) -> None:
        """TELEGRAM_BOT_TOKEN not in environment → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "99999"}, clear=True)

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            send_alert(self._make_alert())

    def test_raises_notification_error_on_http_error(self, mocker) -> None:
        """Non-2xx response from Telegram API → NotificationError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "400 Bad Request"
        )
        mocker.patch("peakguard.notifier.requests.post", return_value=mock_response)

        with pytest.raises(NotificationError, match="400"):
            send_alert(self._make_alert())

    def test_wraps_network_error_in_notification_error(self, mocker) -> None:
        """Network failure is wrapped in NotificationError."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(NotificationError, match="network down"):
            send_alert(self._make_alert())

    def test_wraps_timeout_in_notification_error(self, mocker) -> None:
        """Timeout is wrapped in NotificationError."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.Timeout("read timed out"),
        )

        with pytest.raises(NotificationError, match="timed out"):
            send_alert(self._make_alert())

    def test_sets_request_timeout(self, mocker) -> None:
        """requests.post is called with a timeout parameter."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_alert(self._make_alert())

        call_kwargs = mock_post.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] > 0


class TestSendAlerts:
    """Tests for the send_alerts bulk function."""

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

    def _make_alert(self, ticker: str = "AAPL") -> AlertData:
        """Helper to create a valid AlertData for testing."""
        return AlertData(
            ticker=ticker,
            current_price=150.0,
            peak_price=200.0,
            drawdown_pct=25.0,
        )

    def test_sends_all_alerts_on_success(self, mocker) -> None:
        """Happy path: all alerts are sent successfully."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        alerts = [self._make_alert("AAPL"), self._make_alert("MSFT")]
        results = send_alerts(alerts)

        assert len(results) == 2
        assert results[0].ticker == "AAPL"
        assert results[1].ticker == "MSFT"
        assert mock_post.call_count == 2

    def test_skips_failed_alerts_and_returns_rest(self, mocker) -> None:
        """One alert fails but others succeed — no crash."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        def post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise requests.exceptions.ConnectionError("network down")
            return mock_response

        mocker.patch("peakguard.notifier.requests.post", side_effect=post_side_effect)

        alerts = [
            self._make_alert("AAPL"),
            self._make_alert("MSFT"),
            self._make_alert("GOOG"),
        ]
        results = send_alerts(alerts)

        assert len(results) == 2
        assert results[0].ticker == "AAPL"
        assert results[1].ticker == "GOOG"

    def test_returns_empty_list_when_all_fail(self, mocker) -> None:
        """All alerts fail — returns empty list, no crash."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        alerts = [self._make_alert("AAPL"), self._make_alert("MSFT")]
        results = send_alerts(alerts)

        assert results == []

    def test_returns_empty_list_for_empty_input(self) -> None:
        """Empty alert list returns empty result list."""
        results = send_alerts([])
        assert results == []


class TestATHData:
    """Tests for the ATHData dataclass."""

    def test_creation_with_valid_data(self) -> None:
        """Stores all fields correctly."""
        data = ATHData(
            ticker="AMZN",
            new_peak=234.56,
            peak_date=date(2026, 3, 6),
        )
        assert data.ticker == "AMZN"
        assert data.new_peak == 234.56
        assert data.peak_date == date(2026, 3, 6)

    def test_is_frozen(self) -> None:
        """ATHData instances are immutable."""
        data = ATHData(
            ticker="AMZN",
            new_peak=234.56,
            peak_date=date(2026, 3, 6),
        )
        with pytest.raises(AttributeError):
            data.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        """Empty ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            ATHData(ticker="", new_peak=234.56, peak_date=date(2026, 3, 6))

    def test_rejects_whitespace_ticker(self) -> None:
        """Whitespace-only ticker is a programmer error → ValueError."""
        with pytest.raises(ValueError, match="ticker"):
            ATHData(ticker="   ", new_peak=234.56, peak_date=date(2026, 3, 6))

    def test_rejects_non_positive_new_peak(self) -> None:
        """new_peak must be positive → ValueError."""
        with pytest.raises(ValueError, match="new_peak"):
            ATHData(ticker="AMZN", new_peak=0.0, peak_date=date(2026, 3, 6))

    def test_rejects_negative_new_peak(self) -> None:
        """Negative new_peak is invalid → ValueError."""
        with pytest.raises(ValueError, match="new_peak"):
            ATHData(ticker="AMZN", new_peak=-10.0, peak_date=date(2026, 3, 6))


class TestSendAthAlert:
    """Tests for the send_ath_alert function."""

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

    def _make_ath_data(self) -> ATHData:
        """Helper to create a valid ATHData for testing."""
        return ATHData(
            ticker="AMZN",
            new_peak=234.56,
            peak_date=date(2026, 3, 6),
        )

    def test_sends_post_request_on_success(self, mocker) -> None:
        """Happy path: sends Telegram message and returns without error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_ath_alert(self._make_ath_data())

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://api.telegram.org/bot" in call_args[0][0]
        assert "sendMessage" in call_args[0][0]

    def test_message_contains_ath_details(self, mocker) -> None:
        """Posted message text includes ticker, new peak, and date."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_ath_alert(self._make_ath_data())

        payload = mock_post.call_args[1]["json"]
        text = payload["text"]
        assert "AMZN" in text
        assert "234.56" in text
        assert "2026-03-06" in text

    def test_uses_correct_token_and_chat_id(self, mocker) -> None:
        """URL contains the bot token and payload contains the chat_id."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_ath_alert(self._make_ath_data())

        url = mock_post.call_args[0][0]
        assert "fake-token-123" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "99999"

    def test_raises_value_error_when_token_missing(self, mocker) -> None:
        """Missing TELEGRAM_BOT_TOKEN is a programmer error → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}, clear=False)

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            send_ath_alert(self._make_ath_data())

    def test_raises_value_error_when_chat_id_missing(self, mocker) -> None:
        """Missing TELEGRAM_CHAT_ID is a programmer error → ValueError."""
        mocker.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": ""}, clear=False)

        with pytest.raises(ValueError, match="TELEGRAM_CHAT_ID"):
            send_ath_alert(self._make_ath_data())

    def test_raises_notification_error_on_http_error(self, mocker) -> None:
        """Non-2xx response from Telegram API → NotificationError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "400 Bad Request"
        )
        mocker.patch("peakguard.notifier.requests.post", return_value=mock_response)

        with pytest.raises(NotificationError, match="400"):
            send_ath_alert(self._make_ath_data())

    def test_wraps_network_error_in_notification_error(self, mocker) -> None:
        """Network failure is wrapped in NotificationError."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(NotificationError, match="network down"):
            send_ath_alert(self._make_ath_data())

    def test_wraps_timeout_in_notification_error(self, mocker) -> None:
        """Timeout is wrapped in NotificationError."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.Timeout("read timed out"),
        )

        with pytest.raises(NotificationError, match="timed out"):
            send_ath_alert(self._make_ath_data())

    def test_sets_request_timeout(self, mocker) -> None:
        """requests.post is called with a timeout parameter."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_ath_alert(self._make_ath_data())

        call_kwargs = mock_post.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] > 0


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


class TestSendFetchErrorsAlert:
    """Tests for the send_fetch_errors_alert function."""

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

    def test_does_not_send_when_empty_list(self, mocker) -> None:
        """No errors → no Telegram API call."""
        mock_post = mocker.patch("peakguard.notifier.requests.post")

        send_fetch_errors_alert([])

        mock_post.assert_not_called()

    def test_sends_rate_limit_errors(self, mocker) -> None:
        """Rate limit errors appear in a dedicated section."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        errors = [
            FetchErrorData(
                ticker="AMZN",
                cause=FetchFailureCause.RATE_LIMIT,
                reason="429 Too Many Requests",
            ),
        ]
        send_fetch_errors_alert(errors)

        mock_post.assert_called_once()
        text = mock_post.call_args[1]["json"]["text"]
        assert "Rate Limit" in text
        assert "AMZN" in text

    def test_sends_other_errors(self, mocker) -> None:
        """Non-rate-limit errors appear in a dedicated section."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        errors = [
            FetchErrorData(
                ticker="NVDA",
                cause=FetchFailureCause.EMPTY_DATA,
                reason="no price data returned",
            ),
        ]
        send_fetch_errors_alert(errors)

        mock_post.assert_called_once()
        text = mock_post.call_args[1]["json"]["text"]
        assert "Other" in text
        assert "NVDA" in text

    def test_mixed_errors_have_separate_sections(self, mocker) -> None:
        """Mixed causes produce both rate-limit and other sections."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        errors = [
            FetchErrorData(
                ticker="AMZN",
                cause=FetchFailureCause.RATE_LIMIT,
                reason="429 Too Many Requests",
            ),
            FetchErrorData(
                ticker="NVDA",
                cause=FetchFailureCause.EMPTY_DATA,
                reason="no price data returned",
            ),
            FetchErrorData(
                ticker="GOOG",
                cause=FetchFailureCause.UNKNOWN,
                reason="connection timeout",
            ),
        ]
        send_fetch_errors_alert(errors)

        mock_post.assert_called_once()
        text = mock_post.call_args[1]["json"]["text"]
        assert "Rate Limit" in text
        assert "AMZN" in text
        assert "Other" in text
        assert "NVDA" in text
        assert "GOOG" in text

    def test_raises_notification_error_on_http_failure(self, mocker) -> None:
        """Telegram API failure → NotificationError."""
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        errors = [
            FetchErrorData(
                ticker="AMZN",
                cause=FetchFailureCause.RATE_LIMIT,
                reason="429 Too Many Requests",
            ),
        ]
        with pytest.raises(NotificationError, match="network down"):
            send_fetch_errors_alert(errors)


# ---------------------------------------------------------------------------
# DaysSinceATHAlertData + send_days_since_ath_alert
# ---------------------------------------------------------------------------


class TestDaysSinceATHAlertData:
    """Tests for the DaysSinceATHAlertData dataclass."""

    def test_creation_with_valid_data(self) -> None:
        data = DaysSinceATHAlertData(ticker="AMZN", days=200, limit=180)
        assert data.ticker == "AMZN"
        assert data.days == 200
        assert data.limit == 180

    def test_is_frozen(self) -> None:
        data = DaysSinceATHAlertData(ticker="AMZN", days=200, limit=180)
        with pytest.raises(AttributeError):
            data.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        with pytest.raises(ValueError, match="ticker"):
            DaysSinceATHAlertData(ticker="", days=200, limit=180)


class TestSendDaysSinceATHAlert:
    """Tests for the send_days_since_ath_alert function."""

    @pytest.fixture(autouse=True)
    def _set_env(self, mocker) -> None:
        mocker.patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "fake-token-123", "TELEGRAM_CHAT_ID": "99999"},
        )

    def test_sends_post_request_on_success(self, mocker) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_days_since_ath_alert(
            DaysSinceATHAlertData(ticker="AMZN", days=200, limit=180)
        )

        mock_post.assert_called_once()

    def test_message_contains_details(self, mocker) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_days_since_ath_alert(
            DaysSinceATHAlertData(ticker="AMZN", days=200, limit=180)
        )

        text = mock_post.call_args[1]["json"]["text"]
        assert "AMZN" in text
        assert "200" in text

    def test_raises_notification_error_on_failure(self, mocker) -> None:
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(NotificationError):
            send_days_since_ath_alert(
                DaysSinceATHAlertData(ticker="AMZN", days=200, limit=180)
            )


# ---------------------------------------------------------------------------
# ZScoreAlertData + send_zscore_alert
# ---------------------------------------------------------------------------


class TestZScoreAlertData:
    """Tests for the ZScoreAlertData dataclass."""

    def test_creation_with_valid_data(self) -> None:
        data = ZScoreAlertData(ticker="NVDA", zscore=-2.5, threshold=-2.0)
        assert data.ticker == "NVDA"
        assert data.zscore == -2.5
        assert data.threshold == -2.0

    def test_is_frozen(self) -> None:
        data = ZScoreAlertData(ticker="NVDA", zscore=-2.5, threshold=-2.0)
        with pytest.raises(AttributeError):
            data.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        with pytest.raises(ValueError, match="ticker"):
            ZScoreAlertData(ticker="", zscore=-2.5, threshold=-2.0)


class TestSendZScoreAlert:
    """Tests for the send_zscore_alert function."""

    @pytest.fixture(autouse=True)
    def _set_env(self, mocker) -> None:
        mocker.patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "fake-token-123", "TELEGRAM_CHAT_ID": "99999"},
        )

    def test_sends_post_request_on_success(self, mocker) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_zscore_alert(ZScoreAlertData(ticker="NVDA", zscore=-2.5, threshold=-2.0))

        mock_post.assert_called_once()

    def test_message_contains_details(self, mocker) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_zscore_alert(ZScoreAlertData(ticker="NVDA", zscore=-2.5, threshold=-2.0))

        text = mock_post.call_args[1]["json"]["text"]
        assert "NVDA" in text
        assert "-2.5" in text

    def test_raises_notification_error_on_failure(self, mocker) -> None:
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(NotificationError):
            send_zscore_alert(
                ZScoreAlertData(ticker="NVDA", zscore=-2.5, threshold=-2.0)
            )


# ---------------------------------------------------------------------------
# BounceAlertData + send_bounce_alert
# ---------------------------------------------------------------------------


class TestBounceAlertData:
    """Tests for the BounceAlertData dataclass."""

    def test_creation_with_valid_data(self) -> None:
        data = BounceAlertData(ticker="META", bounce_pct=5.0, min_pct=3.0)
        assert data.ticker == "META"
        assert data.bounce_pct == 5.0
        assert data.min_pct == 3.0

    def test_is_frozen(self) -> None:
        data = BounceAlertData(ticker="META", bounce_pct=5.0, min_pct=3.0)
        with pytest.raises(AttributeError):
            data.ticker = "MSFT"  # type: ignore[misc]

    def test_rejects_empty_ticker(self) -> None:
        with pytest.raises(ValueError, match="ticker"):
            BounceAlertData(ticker="", bounce_pct=5.0, min_pct=3.0)


class TestSendBounceAlert:
    """Tests for the send_bounce_alert function."""

    @pytest.fixture(autouse=True)
    def _set_env(self, mocker) -> None:
        mocker.patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "fake-token-123", "TELEGRAM_CHAT_ID": "99999"},
        )

    def test_sends_post_request_on_success(self, mocker) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_bounce_alert(BounceAlertData(ticker="META", bounce_pct=5.0, min_pct=3.0))

        mock_post.assert_called_once()

    def test_message_contains_details(self, mocker) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = mocker.patch(
            "peakguard.notifier.requests.post", return_value=mock_response
        )

        send_bounce_alert(BounceAlertData(ticker="META", bounce_pct=5.0, min_pct=3.0))

        text = mock_post.call_args[1]["json"]["text"]
        assert "META" in text
        assert "5.0" in text

    def test_raises_notification_error_on_failure(self, mocker) -> None:
        mocker.patch(
            "peakguard.notifier.requests.post",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(NotificationError):
            send_bounce_alert(
                BounceAlertData(ticker="META", bounce_pct=5.0, min_pct=3.0)
            )
