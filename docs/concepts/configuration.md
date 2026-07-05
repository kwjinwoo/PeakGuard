---
id: configuration
title: Configuration
type: concept
status: active
last_verified: 2026-07-05
related:
  - data-contracts.md
  - ../operations.md
code:
  - config/portfolio.yaml
  - src/peakguard/config.py
tests:
  - tests/test_config.py
---

# Configuration

`config/portfolio.yaml` is the user-facing source of truth for tracked assets and alert thresholds. `src/peakguard/config.py` loads it into immutable validated dataclasses.

## Tickers

```yaml
tickers:
  NVDA:
    name: "Nvidia"
    threshold: 15.0
    currency: USD
    asset_type: individual_stock
    portfolio_group: "US Equity"
    thesis_required: true
```

- The mapping key is the yfinance ticker symbol.
- `name` is required and used in reports.
- `threshold` is required and must be in `(0, 100]`.
- `currency` is optional and defaults to `USD`; current formatting explicitly handles `KRW` and otherwise uses the USD format.
- `asset_type` is optional and accepts `individual_stock`, `core_etf`, `bond_etf`, or `gold_proxy`.
- `portfolio_group` optionally maps the asset to a PortfoTrack allocation group.
- `thesis_required` defaults to `false`; only an `individual_stock` may enable it.
- `proxy_for` optionally points from the configured ticker to a canonical US-market ticker with equivalent intended exposure and cannot equal the configured ticker. For example, `360750.KS` uses `proxy_for: SPY`, while prices continue to be fetched from `360750.KS` in KRW.
- Optional string metadata must be non-blank. Omitting all asset metadata preserves legacy price-only behavior.

## Global alert thresholds

```yaml
alert_thresholds:
  days_since_ath_limit: 180
  zscore_threshold: -2.0
  bounce_from_bottom_min: 3.0
```

- `days_since_ath_limit` must be a positive integer.
- `zscore_threshold` must be negative.
- `bounce_from_bottom_min` must be non-negative.

Configuration contains no credentials. Runtime secrets remain environment variables described in [Operations](../operations.md).

When changing this schema, update `src/peakguard/config.py`, `tests/test_config.py`, configuration examples, and every orchestration consumer together.
