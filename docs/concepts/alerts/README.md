---
id: alert-catalog
title: Alert Catalog
type: index
status: active
last_verified: 2026-07-04
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

PeakGuard sends one consolidated daily Telegram report. Only ticker summaries with an active signal or review level are included; fetch failures can be appended separately. Each ticker leads with its [discount review level](../review-levels.md), and a compact data-health section distinguishes successful, partial, and aborted evaluation paths.

Portfolio context does not widen this selection. Compact allocation details enrich a
reportable configured individual stock or ETF, but PeakGuard never lists the
full PortfoTrack portfolio, unrelated allocation groups, or quiet tickers solely due
to available allocation data. See [ADR-0005](../../decisions/0005-scope-portfolio-context-to-reportable-assets.md).

| Signal | Current condition | Implemented in daily report |
| --- | --- | --- |
| MDD | Drawdown is greater than or equal to ticker threshold | Yes |
| ATH update | New rolling ATH is greater than previous rolling ATH | Yes |
| Stale ATH | Days since the in-window high exceed configured limit | Yes |
| Bounce | Recovery from the window low meets or exceeds configured minimum | Yes |
| Fetch failure | yfinance fetch raises `FetchError` | Yes |
| Z-score | Current price is at or below the configured negative Z-score threshold | Yes |
| Portfolio action | A reportable ticker has a usable mapped allocation group | Yes |

Detailed pages:

- [Price and ATH signals](price-signals.md)
- [Fetch failure reporting](fetch-failures.md)

Canonical implementation: `src/peakguard/main.py`, `src/peakguard/mdd_calc.py`, and `src/peakguard/notifier.py`.
