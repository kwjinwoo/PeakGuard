"""Main orchestration module — coordinates the daily MDD check pipeline.

This module ties together all layers: loading configuration, fetching
prices, calculating drawdowns, building per-ticker summaries, and
sending a single consolidated daily Telegram report.
"""

import logging
import os
from datetime import date, timedelta
from pathlib import Path

from peakguard.config import load_alert_thresholds, load_portfolio
from peakguard.errors import FetchError, GistError, NotificationError
from peakguard.fetcher import fetch_history, fetch_price
from peakguard.gist_client import read_gist, write_gist
from peakguard.mdd_calc import (
    calculate_bounce_from_bottom,
    calculate_days_since_ath,
    calculate_drawdown,
    check_threshold,
    get_rolling_ath,
    update_price_history,
)
from peakguard.notifier import (
    FetchErrorData,
    TickerSummary,
    send_daily_summary,
)
from peakguard.storage import ClosingPrice, deserialize_history, serialize_history

__all__ = ["run"]

logger = logging.getLogger(__name__)

_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "portfolio.yaml"
)
_GIST_FILENAME = "peak_prices.csv"
_WINDOW_DAYS = 365


def _load_history_from_gist() -> dict[str, list[ClosingPrice]]:
    """Load price history from the GitHub Gist.

    Returns:
        A dict of ticker → list[ClosingPrice]. Empty dict if the gist
        file does not exist yet (first-run scenario).
    """
    gist_id = os.environ.get("GIST_ID", "")
    if not gist_id:
        raise ValueError("GIST_ID environment variable is required")

    try:
        content = read_gist(gist_id=gist_id, filename=_GIST_FILENAME)
        return deserialize_history(content)
    except GistError:
        logger.info("No existing history found in gist, starting fresh")
        return {}


def _save_history_to_gist(records: dict[str, list[ClosingPrice]]) -> None:
    """Save price history to the GitHub Gist.

    Args:
        records: The price history to persist.
    """
    gist_id = os.environ.get("GIST_ID", "")
    if not gist_id:
        raise ValueError("GIST_ID environment variable is required")

    content = serialize_history(records)
    write_gist(gist_id=gist_id, filename=_GIST_FILENAME, content=content)


def run() -> None:
    """Execute the daily MDD check pipeline with consolidated summary.

    Steps:
        1. Load portfolio configuration from YAML.
        2. Load existing price history from Gist (CSV).
        3. For each ticker:
           a. Bootstrap (fetch 1-year history) if no prior data exists.
           b. Otherwise fetch today's price and append to history.
           c. Compute rolling ATH, drawdown, and metric alerts.
           d. Build a TickerSummary for the consolidated report.
        4. Send a single consolidated daily summary via Telegram.
        5. Save updated history back to Gist.
    """
    configs = load_portfolio(_CONFIG_PATH)
    alert_limits = load_alert_thresholds(_CONFIG_PATH)
    history = _load_history_from_gist()
    fetch_errors: list[FetchErrorData] = []
    summaries: list[TickerSummary] = []
    reference_date: date | None = None

    for cfg in configs:
        ticker = cfg.ticker

        if ticker not in history or not history[ticker]:
            # Bootstrap: fetch 1 year of history for new tickers
            try:
                closing_prices = fetch_history(ticker)
            except FetchError as exc:
                logger.warning("Skipping %s: %s", ticker, exc)
                fetch_errors.append(
                    FetchErrorData(ticker=ticker, cause=exc.cause, reason=str(exc))
                )
                continue

            history[ticker] = closing_prices
            current_price = closing_prices[-1].price
            reference_date = closing_prices[-1].date
            old_ath = None
        else:
            # Daily: compute old ATH, fetch today's price, update history
            previous_date = history[ticker][-1].date
            try:
                old_ath = get_rolling_ath(history[ticker], previous_date, _WINDOW_DAYS)
            except ValueError:
                old_ath = None

            try:
                result = fetch_price(ticker)
            except FetchError as exc:
                logger.warning("Skipping %s: %s", ticker, exc)
                fetch_errors.append(
                    FetchErrorData(ticker=ticker, cause=exc.cause, reason=str(exc))
                )
                continue

            history[ticker] = update_price_history(
                history[ticker],
                ticker=ticker,
                price=result.price,
                today=result.fetched_at,
                window_days=_WINDOW_DAYS,
            )
            current_price = result.price
            reference_date = result.fetched_at

        # Compute new rolling ATH
        new_ath = get_rolling_ath(history[ticker], reference_date, _WINDOW_DAYS)

        # ATH change detection — only flag when ATH actually increased
        ath_updated = old_ath is not None and new_ath > old_ath

        # Build TickerSummary based on whether price is below ATH
        if current_price >= new_ath:
            summary = TickerSummary(
                ticker=ticker,
                name=cfg.name,
                current_price=current_price,
                ath=new_ath,
                mdd_pct=None,
                days_since_ath=None,
                days_since_ath_limit=None,
                bounce_pct=None,
                mdd_alert=False,
                ath_stale_alert=False,
                bounce_alert=False,
                ath_updated=ath_updated,
            )
        else:
            drawdown = calculate_drawdown(current_price, new_ath)
            mdd_alert = check_threshold(drawdown, cfg.threshold)

            # Find ATH entry for days-since-ath calculation
            cutoff = reference_date - timedelta(days=_WINDOW_DAYS)
            ath_entry = max(
                (cp for cp in history[ticker] if cutoff <= cp.date <= reference_date),
                key=lambda cp: cp.price,
            )

            days = calculate_days_since_ath(ath_entry.date, reference_date)
            ath_stale_alert = days > alert_limits.days_since_ath_limit

            bounce = calculate_bounce_from_bottom(current_price, history[ticker])
            bounce_alert = bounce >= alert_limits.bounce_from_bottom_min

            summary = TickerSummary(
                ticker=ticker,
                name=cfg.name,
                current_price=current_price,
                ath=new_ath,
                mdd_pct=drawdown,
                days_since_ath=days,
                days_since_ath_limit=alert_limits.days_since_ath_limit,
                bounce_pct=bounce,
                mdd_alert=mdd_alert,
                ath_stale_alert=ath_stale_alert,
                bounce_alert=bounce_alert,
                ath_updated=ath_updated,
            )

        summaries.append(summary)
        logger.info(
            "Processed %s: price=%.2f, ATH=%.2f, alert=%s",
            ticker,
            current_price,
            new_ath,
            summary.has_alert,
        )

    # Use the last reference_date, or today if all tickers failed
    if reference_date is None:
        reference_date = date.today()

    try:
        send_daily_summary(summaries, reference_date, fetch_errors=fetch_errors)
        logger.info("Daily summary sent successfully")
    except NotificationError as exc:
        logger.warning("Failed to send daily summary: %s", exc)

    _save_history_to_gist(history)
    logger.info("History records updated successfully")
