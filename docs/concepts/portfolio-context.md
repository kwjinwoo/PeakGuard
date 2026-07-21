---
id: portfotrack-context
title: PortfoTrack Allocation Context
type: concept
status: active
last_verified: 2026-07-11
related:
  - configuration.md
  - data-contracts.md
  - ../decisions/0004-separate-price-levels-from-portfolio-actions.md
  - ../roadmap.md
code:
  - src/peakguard/portfolio_context.py
  - config/portfolio.yaml
tests:
  - tests/test_portfolio_context.py
  - tests/test_config.py
---

# PortfoTrack Allocation Context

PeakGuard consumes PortfoTrack's consumer-neutral allocation export as an optional,
read-only local input. PortfoTrack owns amount aggregation, allocation weights,
targets, bounds, drift, and allocation status. PeakGuard validates those facts but
does not recalculate portfolio allocation.

## Local file

The optional path is `config/portfotrack_context.json`. The file contains personal
portfolio amounts and is ignored by Git. If it is absent, the loader returns `None`;
an existing invalid file raises a native configuration error.

The file must come from an explicitly selected PortfoTrack snapshot export. PeakGuard
does not read PortfoTrack persistence files or call PortfoTrack over a network.

## Consumption boundary

The export may contain the complete PortfoTrack allocation, but PeakGuard does not
render that inventory. It looks up only the group mapped from a configured individual
stock or ETF that is already reportable because of an active signal or review level.
Unrelated groups and quiet configured tickers remain absent from the Telegram report.
Portfolio context enriches an alert and cannot create one. See
[ADR-0005](../decisions/0005-scope-portfolio-context-to-reportable-assets.md).

## Schema 1.0

```json
{
  "schema_version": "1.0",
  "snapshot": {
    "date": "2026-07-05",
    "currency": "KRW",
    "total_amount": 10000000
  },
  "assets": [
    {
      "asset_id": "us_equity",
      "current_amount": 6000000,
      "current_weight": 0.6,
      "target_weight": 0.7,
      "target_range": {"lower": 0.65, "upper": 0.75},
      "drift_percentage_points": -10.0,
      "status": "below_tolerance"
    }
  ]
}
```

`asset_id` is the stable cross-tool identity. `TickerConfig.portfolio_group` stores
this ID. Display names are deliberately excluded from identity matching.

Statuses are `below_tolerance`, `within_tolerance`, and `above_tolerance`, with
inclusive bounds. Assets are sorted by `asset_id`. Amounts are non-negative integers;
weights and bounds are ratios in `[0, 1]`. An empty portfolio snapshot remains valid
when current amounts and weights are zero and target facts remain present.

## Validation

`load_portfolio_context()` rejects unsupported versions, malformed JSON, missing or
incorrectly typed fields, duplicate or unsorted IDs, invalid bounds, status or drift
disagreement, total-amount disagreement, and inconsistent current or target weight
totals. Loaded group mappings are immutable.

## Freshness policy

Daily orchestration loads the optional file before any Gist, provider, or Telegram
call and classifies age from `snapshot.date` against the run date:

| Age | State | Allocation guidance |
| ---: | --- | --- |
| 0–7 days | `CURRENT` | Eligible |
| 8–30 days | `STALE` | Eligible only with a stale-data warning |
| 31+ days | `EXPIRED` | Disabled; price-only behavior remains |

A future snapshot date is invalid. A missing file preserves price-only operation.
Existing malformed, unsupported, or internally inconsistent files fail before
external calls rather than being silently ignored.

Current orchestration resolves usable mapped groups and derives portfolio actions.
Telegram formatting renders those facts only for already-reportable configured
stocks and ETFs, with one report-level warning when used context is stale.

Schema 1.0 contains allocation groups, not individual holding tickers. It therefore
cannot add or remove entries in `config/portfolio.yaml`. The tracked-asset CLI is
manual and deliberately does not infer holdings from this aggregate snapshot. A
future synchronization feature requires a separate, explicit PortfoTrack contract
that supplies stable ticker identity and ownership semantics.
