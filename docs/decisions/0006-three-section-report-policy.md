---
id: ADR-0006
title: Organize Reports into Three Review Sections
type: decision
status: accepted
created: 2026-07-11
related:
  - ../roadmap.md
  - ../concepts/review-levels.md
  - ../concepts/portfolio-actions.md
  - ../concepts/alerts/README.md
  - 0004-separate-price-levels-from-portfolio-actions.md
  - 0005-scope-portfolio-context-to-reportable-assets.md
code:
  - src/peakguard/notifier.py
tests:
  - tests/test_notifier.py
---

# ADR-0006: Organize reports into three review sections

- Status: Accepted
- Date: 2026-07-11

## Context

Rendering every active ticker as an equally long block made urgent review items hard
to distinguish from recovery observations and allocation guardrails. The report
needs a stable mobile hierarchy without turning `ReviewLevel` or `PortfolioAction`
into trading instructions.

## Decision

The consolidated Telegram report groups every reportable ticker into exactly one
section, in this order:

1. `Action Review · 집중 검토` contains price conditions that require thesis,
   allocation, or rebalancing review.
2. `Watch Only · 관찰` contains within-range `PortfolioAction.WATCH`, recovery-only
   `ReviewLevel.RECOVERY_WATCH`, and informational signals without a price-review
   level.
3. `No Action · 행동 보류` contains `PortfolioAction.NO_ADD`, where the allocation
   upper guardrail overrides attractive-price wording.

Recovery-only entries use one compact line. Other entries retain separate price,
allocation, and suggested-review lines. Healthy run status uses one line; detailed
health appears only when the run is not fully healthy. Stale allocation context
shows its exact snapshot date and age.

Report language must remain non-prescriptive. Formatting tests reject trading-order
language and protect section order, compact recovery rendering, numeric precision,
health detail behavior, and the Telegram length limit.

## Consequences

- The most consequential manual reviews appear first on mobile.
- Observation and allocation-guardrail outcomes remain visible without competing
  with action-review items.
- `ReviewLevel` and `PortfolioAction` remain separate domain facts; the three
  sections are presentation-only classifications.
- New portfolio actions or review levels require an explicit section mapping and
  corresponding formatting tests.

## Alternatives considered

- One full block per ticker was rejected because repeated labels obscured priority.
- A bounce-specific top-level section was rejected because recovery is an
  observation and fits `Watch Only`.
- Omitting above-range alerts was rejected because the allocation guardrail is
  useful context; `No Action` communicates it without implying a trade.
