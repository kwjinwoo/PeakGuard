---
id: ADR-0003
title: Discount Review Level Precedence
type: decision
status: accepted
created: 2026-07-04
related:
  - ../proposals/PROP-0002-define-discount-review-levels.md
  - ../concepts/review-levels.md
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

# ADR-0003: Discount review level precedence

- Status: Accepted
- Date: 2026-07-04

## Context

PeakGuard needs one review-oriented interpretation of MDD, Z-score, and bounce without becoming a trading recommendation engine. The interpretation must preserve existing thresholds and remain extensible to future asset taxonomy.

## Decision

Use a pure domain function with this precedence:

1. Explicit thesis policy → `THESIS_CHECK`.
2. MDD and Z-score alerts → `DEEP_DISCOUNT`.
3. Z-score alert only → `ATTRACTIVE`.
4. MDD alert only → `WATCH`.
5. Bounce alert only → `RECOVERY_WATCH`.
6. No input → `NONE`.

Bounce is subordinate to discount inputs. Z-score unavailability behaves as no Z-score alert. The report leads with the derived level and retains raw metrics and alert labels as evidence.

## Consequences

- Existing MDD alerts remain reportable as at least `WATCH`.
- Statistically weak prices can be `ATTRACTIVE` without a large ATH drawdown.
- `THESIS_CHECK` is modeled and tested but is not inferred by current orchestration.
- Asset taxonomy can activate thesis policy later without changing price-level precedence.

## Alternatives considered

- New numeric level thresholds would duplicate current alert configuration.
- Price-derived thesis checks would conflate market movement with investment rationale.
- Bounce-first precedence could hide stronger active discount evidence.
