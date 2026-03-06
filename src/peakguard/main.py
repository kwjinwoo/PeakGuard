"""Main orchestration module — coordinates the daily MDD check pipeline.

This module ties together all layers: loading configuration, fetching
prices, calculating drawdowns, sending alerts, and persisting price
history data using a rolling window ATH strategy.
"""

import logging
import os
from datetime import timedelta
from pathlib import Path

from peakguard.config import load_alert_thresholds, load_portfolio
from peakguard.errors import FetchError, GistError, NotificationError
from peakguard.fetcher import fetch_history, fetch_price
from peakguard.gist_client import read_gist, write_gist
from peakguard.mdd_calc import (
    calculate_bounce_from_bottom,
    calculate_days_since_ath,
    calculate_drawdown,
    calculate_price_zscore,
    check_threshold,
    get_rolling_ath,
    update_price_history,
)
from peakguard.notifier import (
    ATHData,
    AlertData,
    BounceAlertData,
    DaysSinceATHAlertData,
    FetchErrorData,
    ZScoreAlertData,
    send_alert,
    send_ath_alert,
    send_bounce_alert,
    send_days_since_ath_alert,
    send_fetch_errors_alert,
    send_zscore_alert,
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
    """Execute the daily MDD check pipeline with rolling window ATH.

    Steps:
        1. Load portfolio configuration from YAML.
        2. Load existing price history from Gist (CSV).
        3. For each ticker:
           a. Bootstrap (fetch 1-year history) if no prior data exists.
           b. Otherwise fetch today's price and append to history.
           c. Detect rolling ATH changes and send ATH alerts.
           d. Calculate drawdown and send MDD alerts if threshold breached.
        4. Send batch fetch error alerts.
        5. Save updated history back to Gist.
    """
    configs = load_portfolio(_CONFIG_PATH)
    alert_limits = load_alert_thresholds(_CONFIG_PATH)
    history = _load_history_from_gist()
    fetch_errors: list[FetchErrorData] = []

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

        # ATH change detection (new high, window expiry, or bootstrap)
        if old_ath is None or new_ath != old_ath:
            cutoff = reference_date - timedelta(days=_WINDOW_DAYS)
            ath_entry = max(
                (cp for cp in history[ticker] if cutoff <= cp.date <= reference_date),
                key=lambda cp: cp.price,
            )
            ath_data = ATHData(
                ticker=ticker, new_peak=new_ath, peak_date=ath_entry.date
            )
            try:
                send_ath_alert(ath_data)
                logger.info("ATH alert: %s → %.2f", ticker, new_ath)
            except NotificationError as exc:
                logger.warning("Failed to send ATH alert for %s: %s", ticker, exc)

        # Skip drawdown check if price is at or above ATH
        if current_price >= new_ath:
            continue

        drawdown = calculate_drawdown(current_price, new_ath)

        if check_threshold(drawdown, cfg.threshold):
            alert = AlertData(
                ticker=ticker,
                current_price=current_price,
                peak_price=new_ath,
                drawdown_pct=drawdown,
            )
            try:
                send_alert(alert)
                logger.info("MDD alert: %s (drawdown: %.2f%%)", ticker, drawdown)
            except NotificationError as exc:
                logger.warning("Failed to send alert for %s: %s", ticker, exc)

        # --- Conditional metric alerts ---
        # Find ATH entry for days-since-ath calculation
        cutoff_metrics = reference_date - timedelta(days=_WINDOW_DAYS)
        ath_entry_metrics = max(
            (
                cp
                for cp in history[ticker]
                if cutoff_metrics <= cp.date <= reference_date
            ),
            key=lambda cp: cp.price,
        )

        # 1. Days since ATH
        days = calculate_days_since_ath(ath_entry_metrics.date, reference_date)
        if days > alert_limits.days_since_ath_limit:
            try:
                send_days_since_ath_alert(
                    DaysSinceATHAlertData(
                        ticker=ticker,
                        days=days,
                        limit=alert_limits.days_since_ath_limit,
                    )
                )
                logger.info("Days-since-ATH alert: %s (%d days)", ticker, days)
            except NotificationError as exc:
                logger.warning(
                    "Failed to send days-since-ATH alert for %s: %s", ticker, exc
                )

        # 2. Price Z-score
        try:
            zscore = calculate_price_zscore(current_price, history[ticker])
            if zscore < alert_limits.zscore_threshold:
                try:
                    send_zscore_alert(
                        ZScoreAlertData(
                            ticker=ticker,
                            zscore=zscore,
                            threshold=alert_limits.zscore_threshold,
                        )
                    )
                    logger.info("Z-score alert: %s (zscore: %.4f)", ticker, zscore)
                except NotificationError as exc:
                    logger.warning(
                        "Failed to send Z-score alert for %s: %s", ticker, exc
                    )
        except ValueError:
            logger.debug("Cannot compute Z-score for %s: insufficient data", ticker)

        # 3. Bounce from bottom
        bounce = calculate_bounce_from_bottom(current_price, history[ticker])
        if bounce >= alert_limits.bounce_from_bottom_min:
            try:
                send_bounce_alert(
                    BounceAlertData(
                        ticker=ticker,
                        bounce_pct=bounce,
                        min_pct=alert_limits.bounce_from_bottom_min,
                    )
                )
                logger.info("Bounce alert: %s (bounce: %.2f%%)", ticker, bounce)
            except NotificationError as exc:
                logger.warning("Failed to send bounce alert for %s: %s", ticker, exc)

    try:
        send_fetch_errors_alert(fetch_errors)
    except NotificationError as exc:
        logger.warning("Failed to send fetch error alert: %s", exc)

    _save_history_to_gist(history)
    logger.info("History records updated successfully")
