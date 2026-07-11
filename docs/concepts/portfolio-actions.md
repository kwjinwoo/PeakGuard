---
id: portfolio-actions
title: Portfolio Actions
type: concept
status: active
last_verified: 2026-07-11
related:
  - review-levels.md
  - portfolio-context.md
  - ../decisions/0004-separate-price-levels-from-portfolio-actions.md
  - ../decisions/0005-scope-portfolio-context-to-reportable-assets.md
  - ../decisions/0006-three-section-report-policy.md
  - ../roadmap.md
code:
  - src/peakguard/portfolio_action.py
  - src/peakguard/main.py
  - src/peakguard/notifier.py
tests:
  - tests/test_portfolio_action.py
  - tests/test_main.py
---

# Portfolio Actions

`PortfolioAction` interprets an existing price-review condition within one mapped
PortfoTrack allocation group. It never changes the price-derived `ReviewLevel`.

## Classification

No action is produced for `ReviewLevel.NONE` or recovery-only
`ReviewLevel.RECOVERY_WATCH`. For allocation-eligible price levels, precedence is:

| Priority | Condition | Portfolio action |
| ---: | --- | --- |
| 1 | Above target range | `NO_ADD` |
| 2 | Deep-discount individual stock with thesis policy | `THESIS_CHECK` |
| 3 | Below-range core, bond, or gold ETF | `REBALANCE_CANDIDATE` |
| 4 | Other below-range asset | `ACTION_REVIEW` |
| 5 | Within target range | `WATCH` |

`NO_ADD` has highest priority so an attractive price cannot weaken an allocation
guardrail. When a deep-discount thesis-required stock is not above range,
`THESIS_CHECK` overrides ordinary below- or within-range guidance.

ETF classification uses `asset_type`, not `proxy_for`. Proxy identity describes
market exposure and does not determine allocation policy.

## Boundary

The pure classifier assumes that freshness and `portfolio_group` resolution have
already succeeded. Daily orchestration resolves the configured stable PortfoTrack
`asset_id` directly and attaches both the group facts and derived action to
`TickerSummary` for current and stale context. Missing, expired, or unknown context
bypasses the classifier and preserves price-only behavior. Telegram rendering remains
separate from classification.

Allocation guidance cannot make a ticker reportable. It may be rendered only for a
configured individual stock or ETF already included by the existing signal and
review-level rules. The formatter must not traverse or summarize all groups in the
PortfoTrack context. Legacy entries without `asset_type` remain price-only even when
they declare a `portfolio_group`.

## Report presentation

For an already-reportable ticker with a derived action, Telegram shows the mapped
group weight, target range, and status on one line, followed by a non-prescriptive
review prompt. `ACTION_REVIEW`, `REBALANCE_CANDIDATE`, and `THESIS_CHECK` appear in
`Action Review`; `WATCH` appears in `Watch Only`; and `NO_ADD` appears in `No Action`
as “추가 배분 보류.” Stale mapped context adds one report warning with the exact
snapshot date and age rather than repeating it for every ticker.
