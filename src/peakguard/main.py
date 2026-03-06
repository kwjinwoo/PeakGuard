"""Main orchestration module — coordinates the daily MDD check pipeline.

This module ties together all layers: loading configuration, fetching
prices, calculating drawdowns, sending alerts, and persisting ATH data.
"""

import logging
import os
from pathlib import Path

from peakguard.config import load_portfolio
from peakguard.errors import FetchError, GistError, NotificationError
from peakguard.fetcher import fetch_price
from peakguard.gist_client import read_gist, write_gist
from peakguard.mdd_calc import calculate_drawdown, check_threshold, update_peak
from peakguard.notifier import ATHData, AlertData, send_alert, send_ath_alert
from peakguard.storage import PeakRecord, deserialize_peaks, serialize_peaks

__all__ = ["run"]

logger = logging.getLogger(__name__)

_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "portfolio.yaml"
)
_GIST_FILENAME = "peak_prices.json"


def _load_peaks_from_gist() -> dict[str, PeakRecord]:
    """Load peak records from the GitHub Gist.

    Returns:
        A dict of ticker → PeakRecord. Empty dict if the gist
        file does not exist yet (first-run scenario).
    """
    gist_id = os.environ.get("GIST_ID", "")
    if not gist_id:
        raise ValueError("GIST_ID environment variable is required")

    try:
        content = read_gist(gist_id=gist_id, filename=_GIST_FILENAME)
        return deserialize_peaks(content)
    except GistError:
        logger.info("No existing peak data found in gist, starting fresh")
        return {}


def _save_peaks_to_gist(records: dict[str, PeakRecord]) -> None:
    """Save peak records to the GitHub Gist.

    Args:
        records: The peak records to persist.
    """
    gist_id = os.environ.get("GIST_ID", "")
    if not gist_id:
        raise ValueError("GIST_ID environment variable is required")

    content = serialize_peaks(records)
    write_gist(gist_id=gist_id, filename=_GIST_FILENAME, content=content)


def run() -> None:
    """Execute the daily MDD check pipeline.

    Steps:
        1. Load portfolio configuration from YAML.
        2. Load existing ATH records from Gist.
        3. For each ticker: fetch price, update peak, check threshold.
        4. Send Telegram alerts for any threshold breaches.
        5. Save updated ATH records back to Gist.
    """
    configs = load_portfolio(_CONFIG_PATH)
    peaks = _load_peaks_from_gist()

    for cfg in configs:
        try:
            result = fetch_price(cfg.ticker)
        except FetchError as exc:
            logger.warning("Skipping %s: %s", cfg.ticker, exc)
            continue

        # Update or initialize peak record
        if cfg.ticker in peaks:
            old_peak = peaks[cfg.ticker]
            peaks[cfg.ticker] = update_peak(result.price, old_peak, result.fetched_at)
            ath_updated = peaks[cfg.ticker].peak_price > old_peak.peak_price
        else:
            peaks[cfg.ticker] = PeakRecord(
                ticker=cfg.ticker,
                peak_price=result.price,
                peak_date=result.fetched_at,
            )
            ath_updated = True

        peak = peaks[cfg.ticker]

        # Send ATH alert if peak was updated or newly initialized
        if ath_updated:
            ath_data = ATHData(
                ticker=cfg.ticker,
                new_peak=peak.peak_price,
                peak_date=peak.peak_date,
            )
            try:
                send_ath_alert(ath_data)
                logger.info(
                    "ATH alert sent for %s (new peak: %.2f)",
                    cfg.ticker,
                    peak.peak_price,
                )
            except NotificationError as exc:
                logger.warning("Failed to send ATH alert for %s: %s", cfg.ticker, exc)

        # Skip drawdown check if price is at or above ATH
        if result.price >= peak.peak_price:
            continue

        drawdown = calculate_drawdown(result.price, peak.peak_price)

        if check_threshold(drawdown, cfg.threshold):
            alert = AlertData(
                ticker=cfg.ticker,
                current_price=result.price,
                peak_price=peak.peak_price,
                drawdown_pct=drawdown,
            )
            try:
                send_alert(alert)
                logger.info(
                    "Alert sent for %s (drawdown: %.2f%%)", cfg.ticker, drawdown
                )
            except NotificationError as exc:
                logger.warning("Failed to send alert for %s: %s", cfg.ticker, exc)

    _save_peaks_to_gist(peaks)
    logger.info("Peak records updated successfully")
