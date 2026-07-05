---
id: PROP-0003
title: PortfoTrack Context MVP
type: proposal
status: accepted
created: 2026-07-04
related:
  - ../decisions/0004-separate-price-levels-from-portfolio-actions.md
  - ../roadmap.md
  - ../concepts/review-levels.md
code:
  - config/portfolio.yaml
  - src/peakguard/config.py
  - src/peakguard/main.py
  - src/peakguard/notifier.py
---

# PortfoTrack Context MVP

## Problem

PeakGuard can identify price discounts but cannot explain whether the corresponding portfolio group is below, within, or above its allocation range. PortfoTrack owns allocation truth and does not track security-level price signals, so neither system can replace the other.

## Evidence

- PeakGuard already derives price-only `ReviewLevel` values.
- `THESIS_CHECK` is reserved for an explicit non-price policy input; current ticker configuration records thesis policy without deriving it from price.
- Existing `tickers` configuration can be extended without breaking price-only operation.
- The MVP input is a local, read-only JSON export rather than direct PortfoTrack integration.

## Candidate direction

- Preserve the `tickers` mapping and add optional `asset_type`, `portfolio_group`, `proxy_for`, and `thesis_required` fields.
- Define `proxy_for` in one direction: the configured price ticker points to the canonical US-market ticker whose exposure it represents. The field does not change the price-fetch symbol.
- Load an optional, versioned `config/portfotrack_context.json` snapshot.
- Consume PortfoTrack's existing `schema_version: "1.0"` export with stable `asset_id` values, rather than defining a competing interchange shape.
- Keep price-derived `ReviewLevel` separate from portfolio-derived `PortfolioAction`.
- Disable allocation guidance when context is at least 31 days old while retaining price-only alerts.
- Treat malformed existing context as a clear configuration error rather than silently ignoring it.

## Alternatives

- Replace `tickers` with `assets` immediately: rejected for the MVP because optional extension preserves compatibility and keeps the migration small.
- Merge portfolio actions into `ReviewLevel`: rejected because price condition and allocation guidance answer different questions.
- Infer thesis failure from price alone: rejected because investment rationale is not observable from market prices.
- Calculate rebalancing amounts: deferred because PortfoTrack remains the allocation and rebalancing source of truth.

## Resolution

Accepted through [ADR-0004](../decisions/0004-separate-price-levels-from-portfolio-actions.md). Phase 3 and Phase 4 in the [roadmap](../roadmap.md) define the implementation checklist.
