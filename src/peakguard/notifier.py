"""Notifier module — sends a consolidated daily summary via the Telegram Bot API.

This module is part of the External Services layer. It handles
all interaction with the Telegram Bot API, building a single daily
report from TickerSummary objects and sending it to a configured chat.
"""

import logging
import os
from dataclasses import dataclass
from datetime import date

import requests

from peakguard.errors import FetchFailureCause, NotificationError

__all__ = [
    "FetchErrorData",
    "TickerSummary",
    "format_daily_summary",
    "send_daily_summary",
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
        currency: The currency code for price display (default: "USD").

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
    currency: str = "USD"

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


def _format_price(price: float, currency: str) -> str:
    """Format a price value with the appropriate currency symbol.

    Args:
        price: The price value to format.
        currency: The currency code (e.g., "USD", "KRW").

    Returns:
        A formatted price string with currency symbol.
    """
    if currency == "KRW":
        return f"\u20a9{price:,.0f}"
    return f"${price:,.2f}"


def _format_ticker_section(summary: TickerSummary) -> str:
    """Build the message section for a single ticker with active alerts.

    Args:
        summary: The ticker's aggregated daily metrics.

    Returns:
        A formatted string block for this ticker.
    """
    # Status line
    status_parts: list[str] = []
    if summary.mdd_alert:
        status_parts.append("📉 MDD 경고")
    if summary.ath_stale_alert:
        status_parts.append("⏸ ATH 지연")
    if summary.bounce_alert:
        status_parts.append("📈 반등 신호")
    if summary.ath_updated:
        status_parts.append("🏔 ATH 갱신")

    lines: list[str] = []
    lines.append(f"{summary.ticker} ({summary.name})")
    lines.append(f"상태: {' '.join(status_parts)}")

    # Price / ATH line
    current = _format_price(summary.current_price, summary.currency)
    ath = _format_price(summary.ath, summary.currency)
    lines.append(f"현재가 / 최고가(ATH): {current} / {ath}")

    # MDD line
    if summary.mdd_pct is not None and summary.mdd_alert:
        lines.append(f"고점 대비 하락률(MDD): -{summary.mdd_pct:.2f}%")

    # ATH stale line
    if (
        summary.ath_stale_alert
        and summary.days_since_ath is not None
        and summary.days_since_ath_limit is not None
    ):
        lines.append(
            f"ATH 갱신 지연: {summary.days_since_ath}일 "
            f"(제한 기준 {summary.days_since_ath_limit}일 초과 - 현금 투입 조절 고려)"
        )

    # Bounce line
    if summary.bounce_pct is not None and summary.bounce_alert:
        lines.append(f"저점 대비 반등률: +{summary.bounce_pct:.2f}% (추세 반전 감지)")

    return "\n".join(lines)


def format_daily_summary(
    summaries: list[TickerSummary],
    report_date: date,
    *,
    fetch_errors: list["FetchErrorData"] | None = None,
) -> str:
    """Build the consolidated daily summary message.

    Pure function — no I/O. Only tickers with active alerts are included.
    If no alerts are active, an all-clear message is produced.

    Args:
        summaries: Per-ticker aggregated metrics for the day.
        report_date: The date of the report.
        fetch_errors: Optional list of fetch errors to append.

    Returns:
        A formatted summary string ready to send via Telegram.
    """
    header = f"📊 PeakGuard Daily Report — {report_date}"
    parts: list[str] = [header, ""]

    alert_summaries = [s for s in summaries if s.has_alert]

    if not alert_summaries:
        parts.append("✅ 모든 티커 이상 없음")
    else:
        for i, summary in enumerate(alert_summaries):
            if i > 0:
                parts.append("")
            parts.append(_format_ticker_section(summary))

    if fetch_errors:
        parts.append("")
        parts.append(_build_fetch_error_message(fetch_errors))

    return "\n".join(parts)


def _get_telegram_config() -> tuple[str, str]:
    """Read and validate Telegram config from environment variables.

    Returns:
        A (token, chat_id) tuple.

    Raises:
        ValueError: If either env var is missing or empty.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set or empty")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID is not set or empty")
    return token, chat_id


def send_daily_summary(
    summaries: list[TickerSummary],
    report_date: date,
    *,
    fetch_errors: list["FetchErrorData"] | None = None,
) -> None:
    """Send the consolidated daily summary via Telegram.

    Builds the summary message using format_daily_summary and sends it
    as a single Telegram message.

    Args:
        summaries: Per-ticker aggregated metrics for the day.
        report_date: The date of the report.
        fetch_errors: Optional list of fetch errors to include.

    Raises:
        ValueError: If Telegram environment variables are missing.
        NotificationError: If the Telegram API call fails.
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = format_daily_summary(summaries, report_date, fetch_errors=fetch_errors)

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
    """Build a human-readable message for batch fetch failures.

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
