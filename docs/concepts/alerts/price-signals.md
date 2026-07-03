---
id: price-signals
title: Price and ATH Signals
type: concept
status: active
last_verified: 2026-07-04
related:
  - README.md
  - ../domain-model.md
  - ../../roadmap.md
code:
  - src/peakguard/mdd_calc.py
  - src/peakguard/main.py
tests:
  - tests/test_mdd_calc.py
  - tests/test_main.py
---

# Price and ATH Signals

## MDD

When the current price is below rolling ATH, drawdown is:

`(rolling ATH - current price) / rolling ATH * 100`

The value is rounded to two decimals. The alert condition is inclusive: `drawdown >= ticker threshold`.

## ATH update

The current implementation flags an update only when the newly computed rolling ATH is greater than the previously computed value. A decrease caused by an old peak expiring is not flagged.

## Stale ATH

The pipeline finds the highest price entry in the current window and calculates calendar days from its date to the reference date. The alert activates only when days are strictly greater than `days_since_ath_limit`.

## Bounce from bottom

Bounce is `(current price - window low) / window low * 100`, rounded to two decimals. The alert activates when bounce is greater than or equal to `bounce_from_bottom_min`.

## Z-score

`calculate_price_zscore()` uses sample standard deviation and requires at least two non-identical history values. The orchestrator evaluates the updated rolling history and activates an alert when `zscore <= zscore_threshold`. Insufficient or zero-variance history produces no Z-score and does not abort the run.

`TickerSummary` carries both the value and alert flag. A Z-score breach makes the ticker reportable; when another alert already makes a ticker reportable, a calculable non-breaching Z-score is still shown as context.
