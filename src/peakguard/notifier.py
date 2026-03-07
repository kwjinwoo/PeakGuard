"""Notifier module — sends MDD and ATH alerts via the Telegram Bot API.

This module is part of the External Services layer. It handles
all interaction with the Telegram Bot API, converting AlertData
and ATHData objects into formatted messages sent to a configured chat.
"""

import logging
import os
from dataclasses import dataclass
from datetime import date

import requests

from peakguard.errors import FetchFailureCause, NotificationError

__all__ = [
    "ATHData",
    "AlertData",
    "BounceAlertData",
    "DaysSinceATHAlertData",
    "FetchErrorData",
    "TickerSummary",
    "ZScoreAlertData",
    "send_alert",
    "send_alerts",
    "send_ath_alert",
    "send_bounce_alert",
    "send_days_since_ath_alert",
    "send_fetch_errors_alert",
    "send_zscore_alert",
]

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class TickerSummary:
    """Immutable container aggregating all daily metrics for a single ticker.

    Used to build the consolidated daily summary message.

    Attributes:
        ticker: The ticker symbol (e.g., "AMZN").
        name: A human-readable name (e.g., "Amazon").
        current_price: The latest close price.
        ath: The rolling all-time high price.
        mdd_pct: Drawdown percentage from ATH, or None if at/above ATH.
        days_since_ath: Calendar days since ATH, or None if not applicable.
        days_since_ath_limit: Configured stale-ATH limit in days, or None.
        bounce_pct: Bounce percentage from 1-year low, or None.
        mdd_alert: True if drawdown breached the configured threshold.
        ath_stale_alert: True if days_since_ath exceeds the limit.
        bounce_alert: True if bounce_pct exceeds the minimum threshold.
        ath_updated: True if a new ATH was reached today.

    Raises:
        ValueError: If ticker is empty.
    """

    ticker: str
    name: str
    current_price: float
    ath: float
    mdd_pct: float | None
    days_since_ath: int | None
    days_since_ath_limit: int | None
    bounce_pct: float | None
    mdd_alert: bool
    ath_stale_alert: bool
    bounce_alert: bool
    ath_updated: bool

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")

    @property
    def has_alert(self) -> bool:
        """Return True if any alert condition is active."""
        return (
            self.mdd_alert
            or self.ath_stale_alert
            or self.bounce_alert
            or self.ath_updated
        )


@dataclass(frozen=True)
class AlertData:
    """Immutable container for a drawdown alert.

    Attributes:
        ticker: The ticker symbol (e.g., "AAPL").
        current_price: The latest close price.
        peak_price: The all-time high price.
        drawdown_pct: The current drawdown percentage (0–100).

    Raises:
        ValueError: If ticker is empty or drawdown_pct is out of range.
    """

    ticker: str
    current_price: float
    peak_price: float
    drawdown_pct: float

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if not 0 <= self.drawdown_pct <= 100:
            raise ValueError(
                f"drawdown_pct must be between 0 and 100, got {self.drawdown_pct}"
            )


def _build_message(alert: AlertData) -> str:
    """Build a human-readable Telegram alert message.

    Args:
        alert: The alert data to format.

    Returns:
        A formatted message string.
    """
    return (
        f"📉 MDD Alert: {alert.ticker}\n"
        f"Current Price: {alert.current_price}\n"
        f"Peak Price (ATH): {alert.peak_price}\n"
        f"Drawdown: {alert.drawdown_pct}%"
    )


def _get_telegram_config() -> tuple[str, str]:
    """Read and validate Telegram configuration from environment variables.

    Returns:
        A tuple of (bot_token, chat_id).

    Raises:
        ValueError: If TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing or empty.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID environment variable is required")

    return token, chat_id


def send_alert(alert: AlertData) -> None:
    """Send a single drawdown alert via Telegram.

    Args:
        alert: The alert data to send.

    Raises:
        ValueError: If Telegram environment variables are missing (programmer error).
        NotificationError: If the Telegram API call fails (network/API error).
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = _build_message(alert)

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise NotificationError(message=str(exc)) from exc


@dataclass(frozen=True)
class ATHData:
    """Immutable container for an all-time-high alert.

    Attributes:
        ticker: The ticker symbol (e.g., "AMZN").
        new_peak: The new all-time high price.
        peak_date: The date the new ATH was reached.

    Raises:
        ValueError: If ticker is empty or new_peak is not positive.
    """

    ticker: str
    new_peak: float
    peak_date: date

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if self.new_peak <= 0:
            raise ValueError(f"new_peak must be positive, got {self.new_peak}")


def _build_ath_message(data: ATHData) -> str:
    """Build a human-readable Telegram ATH notification message.

    Args:
        data: The ATH data to format.

    Returns:
        A formatted message string.
    """
    return (
        f"\U0001f3d4\ufe0f New ATH! {data.ticker}\n"
        f"New Peak: {data.new_peak}\n"
        f"Date: {data.peak_date}"
    )


def send_ath_alert(data: ATHData) -> None:
    """Send a single ATH notification via Telegram.

    Args:
        data: The ATH data to send.

    Raises:
        ValueError: If Telegram environment variables are missing (programmer error).
        NotificationError: If the Telegram API call fails (network/API error).
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = _build_ath_message(data)

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise NotificationError(message=str(exc)) from exc


def send_alerts(alerts: list[AlertData]) -> list[AlertData]:
    """Send multiple drawdown alerts via Telegram.

    Iterates through each alert and calls send_alert individually.
    If a single alert fails, the error is logged and that alert
    is skipped — the remaining alerts are still processed.

    Args:
        alerts: A list of AlertData objects to send.

    Returns:
        A list of AlertData for each successfully sent alert.
        May be shorter than the input list if some alerts failed.
    """
    results: list[AlertData] = []
    for alert in alerts:
        try:
            send_alert(alert)
            results.append(alert)
        except NotificationError as exc:
            logger.warning("Failed to send alert for %s: %s", alert.ticker, exc)
    return results


@dataclass(frozen=True)
class FetchErrorData:
    """Immutable container for a fetch failure notification.

    Attributes:
        ticker: The ticker symbol that failed to fetch.
        cause: The classified cause of the failure.
        reason: A human-readable description of the failure.

    Raises:
        ValueError: If ticker is empty.
    """

    ticker: str
    cause: FetchFailureCause
    reason: str

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")


def _build_fetch_error_message(errors: list[FetchErrorData]) -> str:
    """Build a human-readable Telegram message for batch fetch failures.

    Groups errors by cause: rate-limit errors and other errors are
    listed in separate sections for clarity.

    Args:
        errors: The list of fetch error data to format.

    Returns:
        A formatted message string.
    """
    rate_limit_errors = [e for e in errors if e.cause == FetchFailureCause.RATE_LIMIT]
    other_errors = [e for e in errors if e.cause != FetchFailureCause.RATE_LIMIT]

    parts: list[str] = []

    if rate_limit_errors:
        lines = ["\u26a0\ufe0f Fetch Failed (Rate Limit)"]
        for err in rate_limit_errors:
            lines.append(f"- {err.ticker}: {err.reason}")
        parts.append("\n".join(lines))

    if other_errors:
        lines = ["\u274c Fetch Failed (Other)"]
        for err in other_errors:
            lines.append(f"- {err.ticker}: {err.reason}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def send_fetch_errors_alert(errors: list[FetchErrorData]) -> None:
    """Send a batch fetch-failure alert via Telegram.

    If the error list is empty, no message is sent.

    Args:
        errors: The list of fetch error data to report.

    Raises:
        ValueError: If Telegram environment variables are missing.
        NotificationError: If the Telegram API call fails.
    """
    if not errors:
        return

    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = _build_fetch_error_message(errors)

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise NotificationError(message=str(exc)) from exc


# ---------------------------------------------------------------------------
# DaysSinceATH alert
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DaysSinceATHAlertData:
    """Immutable container for a days-since-ATH alert.

    Attributes:
        ticker: The ticker symbol.
        days: Calendar days elapsed since ATH.
        limit: The configured threshold in days.

    Raises:
        ValueError: If ticker is empty.
    """

    ticker: str
    days: int
    limit: int

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")


def _build_days_since_ath_message(data: DaysSinceATHAlertData) -> str:
    """Build Telegram message for a days-since-ATH alert."""
    return (
        f"\u23f8 ATH Stale: {data.ticker}\n"
        f"Days Since ATH: {data.days}\n"
        f"Limit: {data.limit}\n"
        f"Consider slowing or pausing cash deployment."
    )


def send_days_since_ath_alert(data: DaysSinceATHAlertData) -> None:
    """Send a days-since-ATH warning via Telegram.

    Args:
        data: The alert data to send.

    Raises:
        ValueError: If Telegram environment variables are missing.
        NotificationError: If the Telegram API call fails.
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = _build_days_since_ath_message(data)

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise NotificationError(message=str(exc)) from exc


# ---------------------------------------------------------------------------
# Z-score alert
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZScoreAlertData:
    """Immutable container for a Z-score oversold alert.

    Attributes:
        ticker: The ticker symbol.
        zscore: The current price Z-score.
        threshold: The configured Z-score threshold.

    Raises:
        ValueError: If ticker is empty.
    """

    ticker: str
    zscore: float
    threshold: float

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")


def _build_zscore_message(data: ZScoreAlertData) -> str:
    """Build Telegram message for a Z-score oversold alert."""
    return (
        f"\U0001f3af Oversold Signal: {data.ticker}\n"
        f"Z-score: {data.zscore}\n"
        f"Threshold: {data.threshold}\n"
        f"Price is significantly below the 1-year average."
    )


def send_zscore_alert(data: ZScoreAlertData) -> None:
    """Send a Z-score oversold alert via Telegram.

    Args:
        data: The alert data to send.

    Raises:
        ValueError: If Telegram environment variables are missing.
        NotificationError: If the Telegram API call fails.
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = _build_zscore_message(data)

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise NotificationError(message=str(exc)) from exc


# ---------------------------------------------------------------------------
# Bounce from bottom alert
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BounceAlertData:
    """Immutable container for a bounce-from-bottom alert.

    Attributes:
        ticker: The ticker symbol.
        bounce_pct: Percentage bounce from the 1-year low.
        min_pct: The configured minimum bounce threshold.

    Raises:
        ValueError: If ticker is empty.
    """

    ticker: str
    bounce_pct: float
    min_pct: float

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")


def _build_bounce_message(data: BounceAlertData) -> str:
    """Build Telegram message for a bounce-from-bottom alert."""
    return (
        f"\U0001f4c8 Bounce Signal: {data.ticker}\n"
        f"Bounce from Low: +{data.bounce_pct}%\n"
        f"Minimum Threshold: {data.min_pct}%\n"
        f"Potential trend reversal detected."
    )


def send_bounce_alert(data: BounceAlertData) -> None:
    """Send a bounce-from-bottom alert via Telegram.

    Args:
        data: The alert data to send.

    Raises:
        ValueError: If Telegram environment variables are missing.
        NotificationError: If the Telegram API call fails.
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = _build_bounce_message(data)

    try:
        response = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise NotificationError(message=str(exc)) from exc
