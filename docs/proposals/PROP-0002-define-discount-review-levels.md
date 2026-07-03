---
id: PROP-0002
title: Define Discount Review Levels
type: proposal
status: accepted
created: 2026-07-04
related:
  - ../concepts/review-levels.md
  - ../decisions/0003-discount-review-level-precedence.md
  - ../roadmap.md
code:
  - src/peakguard/mdd_calc.py
  - src/peakguard/main.py
  - src/peakguard/notifier.py
---

# Define Discount Review Levels

## Problem

Independent MDD, Z-score, and bounce flags expose facts but do not give the daily report one stable interpretation. Users must mentally resolve conflicting combinations, and a bounce label can appear beside an active discount condition without clear precedence.

## Evidence

- MDD and Z-score thresholds are already evaluated independently.
- Bounce can be active at the same time as MDD or Z-score.
- The product roadmap requires review prompts rather than automatic trading instructions.
- Asset taxonomy is not yet available, so price behavior cannot safely imply that an investment thesis must be checked.

## Candidate direction

Add a domain `ReviewLevel` and derive it from existing alert booleans. Use MDD-only as `WATCH`, Z-score-only as `ATTRACTIVE`, their intersection as `DEEP_DISCOUNT`, and bounce-only as `RECOVERY_WATCH`. Reserve `THESIS_CHECK` for an explicit policy input and give it highest precedence.

## Alternatives

- Add new numeric discount thresholds: rejected because current per-asset MDD and global Z-score thresholds already define the boundaries.
- Let bounce override discount states: rejected because recovery does not erase statistically weak or deeply drawn-down prices.
- Infer `THESIS_CHECK` from stale ATH or drawdown: rejected because a thesis is a non-price concern and asset taxonomy is not implemented.

## Resolution

Accepted and implemented through [ADR-0003](../decisions/0003-discount-review-level-precedence.md). The exact current decision table is maintained in [Discount Review Levels](../concepts/review-levels.md).
