---
id: discount-review-levels
title: Discount Review Levels
type: concept
status: active
last_verified: 2026-07-04
related:
  - alerts/price-signals.md
  - ../decisions/0003-discount-review-level-precedence.md
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

`THESIS_CHECK` requires `thesis_check_required=True` and overrides every price-derived state. Daily orchestration does not infer this input from price behavior. It remains false until asset taxonomy or another explicit policy source can identify assets that require thesis review.

## Missing Z-score

When Z-score is unavailable because history is insufficient or has zero variance, its alert input is false. MDD can still produce `WATCH`, bounce alone can produce `RECOVERY_WATCH`, and no remaining signal produces `NONE`.

## Reporting

Every reportable ticker shows `검토 단계` before price and metric details. Existing alert labels remain as supporting evidence, while the review level provides the primary interpretation.
