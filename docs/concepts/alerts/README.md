---
id: alert-catalog
title: Alert Catalog
type: index
status: active
last_verified: 2026-07-02
related:
  - price-signals.md
  - fetch-failures.md
  - ../domain-model.md
code:
  - src/peakguard/main.py
  - src/peakguard/mdd_calc.py
  - src/peakguard/notifier.py
tests:
  - tests/test_main.py
  - tests/test_mdd_calc.py
  - tests/test_notifier.py
---

# Alert Catalog

PeakGuard sends one consolidated daily Telegram report. Only ticker summaries with at least one active signal are included; fetch failures can be appended separately.

| Signal | Current condition | Implemented in daily report |
| --- | --- | --- |
| MDD | Drawdown is greater than or equal to ticker threshold | Yes |
| ATH update | New rolling ATH is greater than previous rolling ATH | Yes |
| Stale ATH | Days since the in-window high exceed configured limit | Yes |
| Bounce | Recovery from the window low meets or exceeds configured minimum | Yes |
| Fetch failure | yfinance fetch raises `FetchError` | Yes |
| Z-score | Current price standardized against history | No; calculation and config only |

Detailed pages:

- [Price and ATH signals](price-signals.md)
- [Fetch failure reporting](fetch-failures.md)

Canonical implementation: `src/peakguard/main.py`, `src/peakguard/mdd_calc.py`, and `src/peakguard/notifier.py`.
