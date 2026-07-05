---
id: ADR-0004
title: Separate Price Levels from Portfolio Actions
type: decision
status: accepted
created: 2026-07-04
related:
  - ../proposals/PROP-0003-portfotrack-context-mvp.md
  - ../concepts/review-levels.md
  - ../roadmap.md
code:
  - src/peakguard/mdd_calc.py
  - src/peakguard/config.py
  - src/peakguard/main.py
  - src/peakguard/notifier.py
  - src/peakguard/portfolio_context.py
tests:
  - tests/test_mdd_calc.py
  - tests/test_config.py
  - tests/test_main.py
  - tests/test_notifier.py
  - tests/test_portfolio_context.py
---

# ADR-0004: Separate price levels from portfolio actions

- Status: Accepted
- Date: 2026-07-04

## Context

Price condition and portfolio allocation are independent facts. Combining them into one enum would make a label such as `DEEP_DISCOUNT` ambiguous: it would no longer be clear whether it described price, allocation, or both.

## Decision

Keep `ReviewLevel` as the price-derived result defined by ADR-0003. Add a separate `PortfolioAction` with `ACTION_REVIEW`, `WATCH`, `NO_ADD`, `THESIS_CHECK`, and `REBALANCE_CANDIDATE`.

The MVP uses these rules only when fresh, valid context and a known `portfolio_group` are available:

- Below range: ETF proxies become `REBALANCE_CANDIDATE`; other discounted assets become `ACTION_REVIEW`.
- Within range: discounted assets become `WATCH`.
- Above range: allocation guardrails produce `NO_ADD`.
- An individual stock with `thesis_required=true` and `ReviewLevel.DEEP_DISCOUNT` becomes `THESIS_CHECK`, overriding ordinary portfolio actions.
- Missing context, missing mapping, unknown groups, or context at least 31 days old preserve the price-only report without portfolio guidance.

`THESIS_CHECK` remains an explicit policy outcome: asset configuration opts into thesis review, while deep discount supplies the price condition. Price alone does not imply a broken thesis.

The context contract consumes PortfoTrack's `schema_version: "1.0"` export. Context age is measured from `snapshot.date`: 0–7 days is normal, 8–30 days adds a warning, and 31 or more days disables allocation guidance.

## Consequences

- Reports can show price attractiveness and allocation state as separate facts.
- Existing ticker configuration and price-only operation remain compatible.
- Above-range guidance cannot be weakened by an attractive price label.
- PeakGuard does not calculate trades, optimal weights, or rebalance amounts.
- Future schema changes require an explicit context version migration.

## Alternatives considered

- One combined classification enum would conflate price evidence and portfolio policy.
- An unversioned JSON contract would make future compatibility failures ambiguous.
- Strong warnings without disabling very stale guidance could present obsolete allocation facts as actionable.
- Automatic available-room calculation would move rebalancing ownership into PeakGuard.
