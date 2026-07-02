---
id: configuration
title: Configuration
type: concept
status: active
last_verified: 2026-07-02
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
```

- The mapping key is the yfinance ticker symbol.
- `name` is required and used in reports.
- `threshold` is required and must be in `(0, 100]`.
- `currency` is optional and defaults to `USD`; current formatting explicitly handles `KRW` and otherwise uses the USD format.

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
