---
id: discount-review-levels
title: Discount Review Levels
type: concept
status: active
last_verified: 2026-07-11
related:
  - alerts/price-signals.md
  - portfolio-actions.md
  - ../decisions/0003-discount-review-level-precedence.md
  - ../decisions/0004-separate-price-levels-from-portfolio-actions.md
  - ../decisions/0006-three-section-report-policy.md
  - ../roadmap.md
code:
  - src/peakguard/mdd_calc.py
  - src/peakguard/main.py
  - src/peakguard/notifier.py
tests:
  - tests/test_mdd_calc.py
  - tests/test_main.py
  - tests/test_notifier.py
---

# Discount Review Levels

PeakGuard converts existing price-alert facts into one leading review state. The state is a prompt for manual review, not a buy or sell instruction.

## Decision table

`THESIS_CHECK` has highest precedence when an explicit non-price policy requests it. Otherwise the current MDD, Z-score, and bounce alert booleans map as follows:

| MDD alert | Z-score alert | Bounce alert | Review level | Interpretation |
| --- | --- | --- | --- | --- |
| No | No | No | `NONE` | No discount or recovery review |
| Yes | No | Either | `WATCH` | Drawdown may be ordinary for the asset |
| No | Yes | Either | `ATTRACTIVE` | Statistically weak price without a large ATH drawdown |
| Yes | Yes | Either | `DEEP_DISCOUNT` | Drawdown and statistical weakness agree |
| No | No | Yes | `RECOVERY_WATCH` | Recovery signal without an active discount condition |

Bounce never overrides an active MDD or Z-score condition. Existing inclusive MDD and Z-score thresholds remain unchanged; the review level interprets their boolean results rather than introducing new numeric boundaries.

## Thesis policy

`THESIS_CHECK` requires `thesis_check_required=True` and overrides every price-derived state. Daily orchestration does not infer this input from price behavior, so the price-level input remains false. Current `TickerConfig.thesis_required` selects asset-appropriate report wording; Phase 4 will combine it with portfolio context as a separate `PortfolioAction`.

Portfolio-aware classification remains a separate layer. Future `PortfolioAction.THESIS_CHECK` combines explicit individual-stock thesis policy with `DEEP_DISCOUNT`; it does not change the price-derived `ReviewLevel`. See [ADR-0004](../decisions/0004-separate-price-levels-from-portfolio-actions.md).

## Missing Z-score

When Z-score is unavailable because history is insufficient or has zero variance, its alert input is false. MDD can still produce `WATCH`, bounce alone can produce `RECOVERY_WATCH`, and no remaining signal produces `NONE`.

## Reporting

The formatter uses the review level and optional portfolio action to place each
ticker in `Action Review`, `Watch Only`, or `No Action`. Focused entries show the
review level beside the ticker; recovery-only entries are compressed into one line
under `Watch Only`. Repeated `검토 단계`, `검토 관점`, and status labels are omitted.

When asset metadata is present, a final arrow line adds a non-prescriptive prompt:

- individual stocks with thesis policy prompt an investment-thesis review;
- other individual stocks prompt a fundamentals review;
- core ETFs use next-rebalancing language;
- bond ETFs prompt an interest-rate and duration-risk review; and
- gold proxies prompt a portfolio hedge-allocation review.

Legacy entries without `asset_type` retain the price-only report format.
