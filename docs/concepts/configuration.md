---
id: configuration
title: Configuration
type: concept
status: active
last_verified: 2026-07-11
related:
  - data-contracts.md
  - ../operations.md
code:
  - config/portfolio.yaml
  - src/peakguard/config.py
  - src/peakguard/cli.py
  - pyproject.toml
tests:
  - tests/test_config.py
  - tests/test_cli.py
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
    portfolio_group: us_equity
    thesis_required: true
```

- The mapping key is the yfinance ticker symbol.
- `name` is required and used in reports.
- `threshold` is required and must be in `(0, 100]`.
- `currency` is optional and defaults to `USD`; current formatting explicitly handles `KRW` and otherwise uses the USD format.
- `asset_type` is optional and accepts `individual_stock`, `core_etf`, `bond_etf`, or `gold_proxy`.
- `portfolio_group` optionally maps the asset to a stable PortfoTrack `asset_id`, not its display name.
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

## Tracked-asset CLI

The `peakguard` project script manages the `tickers` mapping without performing
market or network requests:

```bash
uv run peakguard assets list
uv run peakguard assets add AAPL --name "Apple"
uv run peakguard assets update AAPL --thesis-required
uv run peakguard assets remove AAPL
```

`add` defaults to the current US individual-stock policy and accepts explicit
threshold, currency, asset type, portfolio group, thesis policy, and proxy options.
`update` changes only supplied fields and supports paired `--thesis-required` and
`--no-thesis-required` flags. Add rejects duplicates; update and remove reject
unknown tickers. `remove` requires interactive confirmation unless `--yes` is
supplied.

Mutations serialize the complete YAML document to a temporary file, validate both
the ticker and alert-threshold sections through the canonical loaders, flush it, and
atomically replace `config/portfolio.yaml`. Existing key order is retained; comments
and cosmetic YAML formatting are not part of the persisted contract. Removing a
ticker does not delete its historical rows from the remote Gist.

The root [README](../../README.md#tracked-asset-cli) is the user-facing command and
option reference.

When changing this schema, update `src/peakguard/config.py`, `tests/test_config.py`, configuration examples, and every orchestration consumer together.
