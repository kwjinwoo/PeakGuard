---
id: domain-model
title: Domain Model
type: concept
status: active
last_verified: 2026-07-02
related:
  - data-contracts.md
  - alerts/README.md
  - glossary.md
code:
  - src/peakguard/mdd_calc.py
  - src/peakguard/storage.py
tests:
  - tests/test_mdd_calc.py
  - tests/test_storage.py
  - tests/test_main.py
---

# Domain Model

PeakGuard evaluates daily closing prices over a rolling 365-calendar-day window.

## Core concepts

- `ClosingPrice`: immutable ticker, trading date, and positive close price.
- Price history: records for one ticker, ordered by date and upserted by trading date.
- Rolling ATH: maximum close within `[reference_date - 365 days, reference_date]`.
- MDD: percentage decline from the rolling ATH to the current close.
- Threshold breach: `drawdown >= configured threshold`; equality counts as a breach.

ATH in this project is not a lifetime maximum. Old highs naturally expire from the rolling window.

## Daily update invariants

- A ticker without stored history is bootstrapped with one year of yfinance closes.
- An existing ticker fetches only the latest close.
- A record for the same trading date is replaced rather than duplicated.
- Entries outside the inclusive rolling window are removed.
- Invalid values and impossible domain states raise native exceptions rather than integration errors.

Canonical implementation: `src/peakguard/mdd_calc.py` and `src/peakguard/storage.py`.
Canonical tests: `tests/test_mdd_calc.py`, `tests/test_storage.py`, and `tests/test_main.py`.

See [Alert catalog](alerts/README.md), [Data contracts](data-contracts.md), and [Glossary](glossary.md).
