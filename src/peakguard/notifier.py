"""Notifier module — sends a consolidated daily summary via the Telegram Bot API.

This module is part of the External Services layer. It handles
all interaction with the Telegram Bot API, building a single daily
report from TickerSummary objects and sending it to a configured chat.
"""

import logging
import os
from dataclasses import dataclass
from datetime import date
from enum import Enum

import requests

from peakguard.config import AssetType
from peakguard.errors import FetchFailureCause, NotificationError
from peakguard.mdd_calc import ReviewLevel
from peakguard.portfolio_action import PortfolioAction
from peakguard.portfolio_context import AllocationGroup, AllocationStatus

__all__ = [
    "FetchErrorData",
    "HealthStatus",
    "RunHealth",
    "TickerSummary",
    "format_daily_summary",
    "send_daily_summary",
]

logger = logging.getLogger(__name__)

_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
_REQUEST_TIMEOUT_SECONDS = 10
_ALLOCATION_STATUS_LABELS = {
    AllocationStatus.BELOW_TOLERANCE: "목표 하단 미만",
    AllocationStatus.WITHIN_TOLERANCE: "목표 범위 내",
    AllocationStatus.ABOVE_TOLERANCE: "목표 상단 초과",
}
_PORTFOLIO_ACTION_LABELS = {
    PortfolioAction.REBALANCE_CANDIDATE: "다음 리밸런싱 검토",
    PortfolioAction.ACTION_REVIEW: "배분 여력 검토",
    PortfolioAction.WATCH: "관찰 유지",
    PortfolioAction.NO_ADD: "추가 배분 보류",
    PortfolioAction.THESIS_CHECK: "투자 논거 우선 점검",
}


class HealthStatus(Enum):
    """Status of one external operation in the daily pipeline."""

    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_ATTEMPTED = "not attempted"


@dataclass(frozen=True)
class RunHealth:
    """Immutable health facts for one daily PeakGuard execution.

    Attributes:
        fetch_succeeded: Number of assets whose price fetch completed.
        fetch_failed: Number of assets whose price fetch failed.
        gist_read: Outcome of loading persisted history.
        gist_write: Outcome of writing updated history.
        signals_evaluated: Whether any price signals were evaluated.
        history_modified: Whether remote history was updated successfully.

    Raises:
        ValueError: If either fetch count is negative.
    """

    fetch_succeeded: int
    fetch_failed: int
    gist_read: HealthStatus
    gist_write: HealthStatus
    signals_evaluated: bool
    history_modified: bool

    def __post_init__(self) -> None:
        if self.fetch_succeeded < 0 or self.fetch_failed < 0:
            raise ValueError("fetch counts must be non-negative")

    @property
    def fetch_status(self) -> HealthStatus:
        """Derive aggregate price-fetch health from success and failure counts."""
        if self.fetch_succeeded == 0 and self.fetch_failed == 0:
            return HealthStatus.NOT_ATTEMPTED
        if self.fetch_failed == 0:
            return HealthStatus.SUCCEEDED
        if self.fetch_succeeded == 0:
            return HealthStatus.FAILED
        return HealthStatus.PARTIAL


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
        zscore: Current price Z-score, or None when it cannot be calculated.
        zscore_alert: True if Z-score meets the configured low-price threshold.
        review_level: Highest-priority investment-review state.
        asset_type: Optional category used to select review language.
        thesis_required: Whether an individual stock requires thesis review.
        allocation_group: Resolved PortfoTrack allocation facts, when usable.
        portfolio_action: Allocation guidance derived separately from price state.
        portfolio_context_stale: Whether mapped allocation facts are 8–30 days old.

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
    zscore: float | None = None
    zscore_alert: bool = False
    review_level: ReviewLevel = ReviewLevel.NONE
    asset_type: AssetType | None = None
    thesis_required: bool = False
    allocation_group: AllocationGroup | None = None
    portfolio_action: PortfolioAction | None = None
    portfolio_context_stale: bool = False

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
            or self.zscore_alert
            or self.review_level != ReviewLevel.NONE
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


def _asset_review_prompt(summary: TickerSummary) -> str | None:
    """Return a non-prescriptive review prompt for the configured asset type.

    Args:
        summary: The ticker summary whose asset policy selects the wording.

    Returns:
        An asset-appropriate prompt, or ``None`` for legacy untyped assets.
    """
    if summary.asset_type is AssetType.INDIVIDUAL_STOCK:
        if summary.thesis_required:
            return "투자 논거를 점검하세요."
        return "기업 펀더멘털을 점검하세요."
    if summary.asset_type is AssetType.CORE_ETF:
        return "다음 리밸런싱에서 편입 비중을 검토하세요."
    if summary.asset_type is AssetType.BOND_ETF:
        return "금리와 듀레이션 위험을 점검하세요."
    if summary.asset_type is AssetType.GOLD_PROXY:
        return "포트폴리오 헤지 배분을 점검하세요."
    return None


def _format_portfolio_context(summary: TickerSummary) -> list[str]:
    """Format compact allocation facts for one already-reportable ticker.

    Args:
        summary: Reportable ticker with optional mapped allocation guidance.

    Returns:
        Two compact lines, or an empty list when no action can be interpreted.
    """
    group = summary.allocation_group
    action = summary.portfolio_action
    if group is None or action is None:
        return []
    return [
        f"배분: {group.asset_id} {group.current_weight:.1%} · "
        f"목표 {group.target_lower:.1%}–{group.target_upper:.1%} · "
        f"{_ALLOCATION_STATUS_LABELS[group.status]}",
        f"배분 검토: {_PORTFOLIO_ACTION_LABELS[action]}",
    ]


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
    if summary.zscore_alert:
        status_parts.append("📐 Z-score 경고")

    lines: list[str] = []
    lines.append(f"{summary.ticker} ({summary.name})")
    lines.append(f"검토 단계: {summary.review_level.value}")
    review_prompt = _asset_review_prompt(summary)
    if review_prompt is not None:
        lines.append(f"검토 관점: {review_prompt}")
    lines.extend(_format_portfolio_context(summary))
    lines.append(f"상태: {' '.join(status_parts)}")

    # Price / ATH line
    current = _format_price(summary.current_price, summary.currency)
    ath = _format_price(summary.ath, summary.currency)
    lines.append(f"현재가 / 최고가(ATH): {current} / {ath}")

    # MDD line
    if summary.mdd_pct is not None and summary.mdd_alert:
        lines.append(f"고점 대비 하락률(MDD): -{summary.mdd_pct:.2f}%")

    if summary.zscore is not None:
        lines.append(f"Z-score: {summary.zscore:.4f}")

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
    data_health: RunHealth | None = None,
) -> str:
    """Build the consolidated daily summary message.

    Pure function — no I/O. Only tickers with active alerts are included.
    If no alerts are active, an all-clear message is produced.

    Args:
        summaries: Per-ticker aggregated metrics for the day.
        report_date: The date of the report.
        fetch_errors: Optional list of fetch errors to append.
        data_health: Optional execution health facts to append.

    Returns:
        A formatted summary string ready to send via Telegram.
    """
    header = f"📊 PeakGuard Daily Report — {report_date}"
    parts: list[str] = [header, ""]

    alert_summaries = [s for s in summaries if s.has_alert]

    if data_health is not None and not data_health.signals_evaluated:
        parts.append("⚠️ 가격 신호를 평가하지 않음")
    elif not alert_summaries:
        parts.append("✅ 모든 티커 이상 없음")
    else:
        for i, summary in enumerate(alert_summaries):
            if i > 0:
                parts.append("")
            parts.append(_format_ticker_section(summary))
        if any(
            summary.portfolio_context_stale
            and summary.allocation_group is not None
            and summary.portfolio_action is not None
            for summary in alert_summaries
        ):
            parts.append("")
            parts.append("⚠️ PortfoTrack 배분 정보가 오래되었습니다 (8–30일 경과).")

    if fetch_errors:
        parts.append("")
        parts.append(_build_fetch_error_message(fetch_errors))

    if data_health is not None:
        parts.append("")
        parts.append(_format_data_health(data_health))

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
    data_health: RunHealth | None = None,
) -> None:
    """Send the consolidated daily summary via Telegram.

    Builds the summary message using format_daily_summary and sends it
    as a single Telegram message.

    Args:
        summaries: Per-ticker aggregated metrics for the day.
        report_date: The date of the report.
        fetch_errors: Optional list of fetch errors to include.
        data_health: Optional execution health facts to include.

    Raises:
        ValueError: If Telegram environment variables are missing.
        NotificationError: If the Telegram API call fails.
    """
    token, chat_id = _get_telegram_config()
    url = _TELEGRAM_API_URL.format(token=token)
    message = format_daily_summary(
        summaries,
        report_date,
        fetch_errors=fetch_errors,
        data_health=data_health,
    )

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


def _format_data_health(health: RunHealth) -> str:
    """Build the compact data-health section for a daily report.

    Args:
        health: Execution health facts to format.

    Returns:
        A human-readable data-health block.
    """
    signal_status = "evaluated" if health.signals_evaluated else "not evaluated"
    history_status = "updated" if health.history_modified else "not modified"
    return "\n".join(
        [
            "Data Health",
            f"- Price fetch: {health.fetch_status.value} "
            f"({health.fetch_succeeded} succeeded, {health.fetch_failed} failed)",
            f"- Gist read: {health.gist_read.value}",
            f"- Gist write: {health.gist_write.value}",
            f"- Signals: {signal_status}",
            f"- Remote history: {history_status}",
        ]
    )


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
