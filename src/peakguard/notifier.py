"""Notifier module — sends MDD alerts via the Telegram Bot API.

This module is part of the External Services layer. It handles
all interaction with the Telegram Bot API, converting AlertData
objects into formatted messages sent to a configured chat.
"""

import logging
import os
from dataclasses import dataclass

import requests

from peakguard.errors import NotificationError

__all__ = ["AlertData", "send_alert", "send_alerts"]

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT_SECONDS = 10


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
