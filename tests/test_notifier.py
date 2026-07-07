"""Tests for the notifier module — TickerSummary, format_daily_summary, send_daily_summary."""

import os
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from peakguard.config import AssetType
from peakguard.errors import FetchFailureCause, NotificationError
from peakguard.mdd_calc import ReviewLevel
from peakguard.notifier import (
    FetchErrorData,
    HealthStatus,
    RunHealth,
    TickerSummary,
    format_daily_summary,
    send_daily_summary,
)
from peakguard.portfolio_action import PortfolioAction
from peakguard.portfolio_context import AllocationGroup, AllocationStatus


def _allocation_group(
    *,
    asset_id: str = "us_equity",
    status: AllocationStatus = AllocationStatus.ABOVE_TOLERANCE,
) -> AllocationGroup:
    """Build allocation facts for notifier formatting tests."""
    return AllocationGroup(
        asset_id=asset_id,
        current_amount=180,
        current_weight=0.18,
        target_weight=0.15,
        target_lower=0.14,
        target_upper=0.17,
        drift_percentage_points=3.0,
        status=status,
    )


class TestRunHealth:
    """Tests for immutable daily execution health."""

    def test_derives_partial_fetch_status(self) -> None:
        health = RunHealth(
            fetch_succeeded=1,
            fetch_failed=1,
            gist_read=HealthStatus.SUCCEEDED,
            gist_write=HealthStatus.SUCCEEDED,
            signals_evaluated=True,
            history_modified=True,
        )

        assert health.fetch_status == HealthStatus.PARTIAL

    def test_rejects_negative_fetch_count(self) -> None:
        with pytest.raises(ValueError, match="fetch counts"):
            RunHealth(
                fetch_succeeded=-1,
                fetch_failed=0,
                gist_read=HealthStatus.SUCCEEDED,
                gist_write=HealthStatus.SUCCEEDED,
                signals_evaluated=True,
                history_modified=True,
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

    def test_default_currency_is_usd(self) -> None:
        """Currency defaults to USD when not specified."""
        summary = TickerSummary(
            ticker="AMZN",
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
        assert summary.currency == "USD"

    def test_custom_currency_krw(self) -> None:
        """Currency can be set to KRW."""
        summary = TickerSummary(
            ticker="360750.KS",
            name="TIGER \ubbf8\uad6dS&P500",
            current_price=15280.0,
            ath=18000.0,
            mdd_pct=None,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            currency="KRW",
        )
        assert summary.currency == "KRW"

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

    def test_has_alert_true_when_zscore_alert(self) -> None:
        """A statistically low price makes the summary reportable."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=80.0,
            ath=140.0,
            mdd_pct=42.86,
            days_since_ath=30,
            days_since_ath_limit=180,
            bounce_pct=0.0,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            zscore=-2.53,
            zscore_alert=True,
        )

        assert summary.has_alert is True

    def test_has_alert_true_when_review_level_requires_attention(self) -> None:
        """A policy-driven thesis review is reportable without a price flag."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=100.0,
            ath=100.0,
            mdd_pct=None,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            review_level=ReviewLevel.THESIS_CHECK,
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

    def test_reportable_ticker_shows_compact_portfolio_context(self) -> None:
        """Mapped allocation facts enrich an existing ticker alert compactly."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=80.0,
            ath=100.0,
            mdd_pct=20.0,
            days_since_ath=30,
            days_since_ath_limit=180,
            bounce_pct=0.0,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            review_level=ReviewLevel.ATTRACTIVE,
            asset_type=AssetType.INDIVIDUAL_STOCK,
            allocation_group=_allocation_group(),
            portfolio_action=PortfolioAction.NO_ADD,
        )

        result = format_daily_summary([summary], date(2026, 7, 7))

        assert "배분: us_equity 18.0% · 목표 14.0%–17.0% · 목표 상단 초과" in result
        assert "배분 검토: 추가 배분 보류" in result

    @pytest.mark.parametrize(
        ("action", "label"),
        [
            (PortfolioAction.REBALANCE_CANDIDATE, "다음 리밸런싱 검토"),
            (PortfolioAction.ACTION_REVIEW, "배분 여력 검토"),
            (PortfolioAction.WATCH, "관찰 유지"),
            (PortfolioAction.NO_ADD, "추가 배분 보류"),
            (PortfolioAction.THESIS_CHECK, "투자 논거 우선 점검"),
        ],
    )
    def test_portfolio_action_uses_non_prescriptive_review_language(
        self, action: PortfolioAction, label: str
    ) -> None:
        """Portfolio actions render as review prompts rather than trade orders."""
        summary = TickerSummary(
            ticker="AMZN",
            name="Amazon",
            current_price=80.0,
            ath=100.0,
            mdd_pct=20.0,
            days_since_ath=30,
            days_since_ath_limit=180,
            bounce_pct=0.0,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            review_level=ReviewLevel.ATTRACTIVE,
            asset_type=AssetType.INDIVIDUAL_STOCK,
            allocation_group=_allocation_group(),
            portfolio_action=action,
        )

        result = format_daily_summary([summary], date(2026, 7, 7))

        assert f"배분 검토: {label}" in result

    def test_configured_universe_worst_case_fits_one_telegram_message(self) -> None:
        """Seven fully alerted configured assets remain under Telegram's limit."""
        summaries = [
            TickerSummary(
                ticker=ticker,
                name=ticker,
                current_price=80.0,
                ath=100.0,
                mdd_pct=20.0,
                days_since_ath=200,
                days_since_ath_limit=180,
                bounce_pct=10.0,
                mdd_alert=True,
                ath_stale_alert=True,
                bounce_alert=True,
                ath_updated=True,
                zscore=-2.5,
                zscore_alert=True,
                review_level=ReviewLevel.DEEP_DISCOUNT,
                asset_type=AssetType.CORE_ETF,
                allocation_group=_allocation_group(),
                portfolio_action=PortfolioAction.NO_ADD,
                portfolio_context_stale=True,
            )
            for ticker in (
                "AMZN",
                "MSFT",
                "META",
                "NVDA",
                "GOOGL",
                "360750.KS",
                "133690.KS",
            )
        ]

        result = format_daily_summary(summaries, date(2026, 7, 7))

        assert len(result.encode("utf-16-le")) // 2 <= 4096

    def test_quiet_ticker_and_unrelated_group_are_not_rendered(self) -> None:
        """Allocation context cannot widen the existing reportable ticker set."""
        quiet = TickerSummary(
            ticker="MSFT",
            name="Microsoft",
            current_price=100.0,
            ath=100.0,
            mdd_pct=None,
            days_since_ath=None,
            days_since_ath_limit=None,
            bounce_pct=None,
            mdd_alert=False,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            asset_type=AssetType.INDIVIDUAL_STOCK,
            allocation_group=_allocation_group(asset_id="unrelated_cash"),
            portfolio_action=PortfolioAction.WATCH,
        )

        result = format_daily_summary([quiet], date(2026, 7, 7))

        assert "모든 티커 이상 없음" in result
        assert "MSFT" not in result
        assert "unrelated_cash" not in result
        assert "배분 검토" not in result

    def test_stale_portfolio_warning_is_shown_once(self) -> None:
        """A stale warning is global even when several reportable tickers use it."""
        summaries = [
            TickerSummary(
                ticker=ticker,
                name=ticker,
                current_price=80.0,
                ath=100.0,
                mdd_pct=20.0,
                days_since_ath=30,
                days_since_ath_limit=180,
                bounce_pct=0.0,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
                review_level=ReviewLevel.ATTRACTIVE,
                asset_type=AssetType.CORE_ETF,
                allocation_group=_allocation_group(),
                portfolio_action=PortfolioAction.NO_ADD,
                portfolio_context_stale=True,
            )
            for ticker in ("SPY", "QQQ")
        ]

        result = format_daily_summary(summaries, date(2026, 7, 7))

        assert result.count("PortfoTrack 배분 정보가 오래되었습니다") == 1

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

    def test_healthy_run_includes_data_health(self) -> None:
        health = RunHealth(
            fetch_succeeded=2,
            fetch_failed=0,
            gist_read=HealthStatus.SUCCEEDED,
            gist_write=HealthStatus.SUCCEEDED,
            signals_evaluated=True,
            history_modified=True,
        )

        result = format_daily_summary([], date(2026, 3, 7), data_health=health)

        assert "Data Health" in result
        assert "Price fetch: succeeded (2 succeeded, 0 failed)" in result
        assert "Gist read: succeeded" in result
        assert "Gist write: succeeded" in result
        assert "Signals: evaluated" in result
        assert "Remote history: updated" in result

    def test_partial_fetch_is_not_presented_as_healthy(self) -> None:
        health = RunHealth(
            fetch_succeeded=1,
            fetch_failed=1,
            gist_read=HealthStatus.SUCCEEDED,
            gist_write=HealthStatus.SUCCEEDED,
            signals_evaluated=True,
            history_modified=True,
        )

        result = format_daily_summary([], date(2026, 3, 7), data_health=health)

        assert "Price fetch: partial (1 succeeded, 1 failed)" in result
        assert "Price fetch: succeeded" not in result

    def test_fatal_persistence_health_suppresses_all_clear(self) -> None:
        health = RunHealth(
            fetch_succeeded=0,
            fetch_failed=0,
            gist_read=HealthStatus.FAILED,
            gist_write=HealthStatus.NOT_ATTEMPTED,
            signals_evaluated=False,
            history_modified=False,
        )

        result = format_daily_summary([], date(2026, 3, 7), data_health=health)

        assert "가격 신호를 평가하지 않음" in result
        assert "이상 없음" not in result
        assert "Gist read: failed" in result
        assert "Gist write: not attempted" in result
        assert "Signals: not evaluated" in result
        assert "Remote history: not modified" in result

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

    def test_zscore_alert_shows_status_and_value(self) -> None:
        """A breached Z-score threshold is visible in the ticker section."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=80.0,
                ath=140.0,
                mdd_pct=42.86,
                days_since_ath=30,
                days_since_ath_limit=180,
                bounce_pct=0.0,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
                zscore=-2.53,
                zscore_alert=True,
            )
        ]

        result = format_daily_summary(summaries, date(2026, 3, 7))

        assert "Z-score 경고" in result
        assert "Z-score: -2.5300" in result

    @pytest.mark.parametrize(
        "level",
        [
            ReviewLevel.WATCH,
            ReviewLevel.ATTRACTIVE,
            ReviewLevel.DEEP_DISCOUNT,
            ReviewLevel.THESIS_CHECK,
            ReviewLevel.RECOVERY_WATCH,
        ],
    )
    def test_review_level_precedes_raw_metrics(self, level: ReviewLevel) -> None:
        """The review state leads each reportable ticker section."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=80.0,
                ath=140.0,
                mdd_pct=42.86,
                days_since_ath=30,
                days_since_ath_limit=180,
                bounce_pct=0.0,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
                zscore=-2.53,
                zscore_alert=True,
                review_level=level,
            )
        ]

        result = format_daily_summary(summaries, date(2026, 3, 7))

        level_line = f"검토 단계: {level.value}"
        assert level_line in result
        assert result.index(level_line) < result.index("현재가 / 최고가")
        assert "buy" not in result.lower()

    @pytest.mark.parametrize(
        ("asset_type", "thesis_required", "expected"),
        [
            (AssetType.INDIVIDUAL_STOCK, True, "투자 논거를 점검"),
            (AssetType.INDIVIDUAL_STOCK, False, "기업 펀더멘털을 점검"),
            (AssetType.CORE_ETF, False, "다음 리밸런싱에서 편입 비중을 검토"),
            (AssetType.BOND_ETF, False, "금리와 듀레이션 위험을 점검"),
            (AssetType.GOLD_PROXY, False, "포트폴리오 헤지 배분을 점검"),
        ],
    )
    def test_uses_asset_appropriate_review_language(
        self, asset_type: AssetType, thesis_required: bool, expected: str
    ) -> None:
        summary = TickerSummary(
            ticker="TEST",
            name="Test asset",
            current_price=80.0,
            ath=100.0,
            mdd_pct=20.0,
            days_since_ath=30,
            days_since_ath_limit=180,
            bounce_pct=0.0,
            mdd_alert=True,
            ath_stale_alert=False,
            bounce_alert=False,
            ath_updated=False,
            review_level=ReviewLevel.ATTRACTIVE,
            asset_type=asset_type,
            thesis_required=thesis_required,
        )

        result = format_daily_summary([summary], date(2026, 3, 7))

        assert f"검토 관점: {expected}" in result
        for forbidden in ("buy now", "strong buy", "매수", "매도", "반드시 추가"):
            assert forbidden not in result.lower()

    def test_non_alert_zscore_is_context_for_another_alert(self) -> None:
        """Reportable tickers show Z-score even when it did not breach."""
        summaries = [
            TickerSummary(
                ticker="AMZN",
                name="Amazon",
                current_price=110.0,
                ath=140.0,
                mdd_pct=21.43,
                days_since_ath=30,
                days_since_ath_limit=180,
                bounce_pct=10.0,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
                zscore=-1.25,
                zscore_alert=False,
            )
        ]

        result = format_daily_summary(summaries, date(2026, 3, 7))

        assert "Z-score 경고" not in result
        assert "Z-score: -1.2500" in result

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

    def test_krw_ticker_shows_won_symbol(self) -> None:
        """KRW ticker prices display with \u20a9 symbol and integer format."""
        summaries = [
            TickerSummary(
                ticker="360750.KS",
                name="TIGER \ubbf8\uad6dS&P500",
                current_price=15280.0,
                ath=18000.0,
                mdd_pct=15.11,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=True,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=False,
                currency="KRW",
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "\u20a915,280" in result
        assert "\u20a918,000" in result

    def test_usd_ticker_shows_dollar_symbol(self) -> None:
        """USD ticker prices display with $ symbol and 2 decimal places."""
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
                currency="USD",
            ),
        ]
        result = format_daily_summary(summaries, date(2026, 3, 7))
        assert "$213.21" in result
        assert "$254.00" in result


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
