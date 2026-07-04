# Configuration Guide

`portfolio.yaml` is the user-facing source of truth for tracked assets and alert limits. Keep it human-readable and compatible with the immutable models and loaders in `src/peakguard/config.py`.

## Schema

- `tickers` maps each yfinance ticker symbol to required `name` and positive `threshold` in `(0, 100]`, plus optional `currency` (default `USD`), `asset_type`, `portfolio_group`, `thesis_required`, and `proxy_for`. Quote ticker keys when YAML parsing could alter their meaning.
- `asset_type`, when present, is one of `individual_stock`, `core_etf`, `bond_etf`, or `gold_proxy`. Only `individual_stock` may set `thesis_required: true`. Optional string metadata must be non-blank, and `proxy_for` cannot equal its ticker key.
- `alert_thresholds.days_since_ath_limit` is a positive integer.
- `alert_thresholds.zscore_threshold` is negative.
- `alert_thresholds.bounce_from_bottom_min` is non-negative.

Do not place secrets, Gist identifiers, Telegram identifiers, or environment-specific credentials in YAML. Those remain environment variables injected by GitHub Actions.

When the schema changes, update the loader models and validation, configuration tests, README example, and any orchestration consumer in the same change. Adding or removing a ticker normally requires only a YAML edit; do not hard-code portfolio membership in Python.
