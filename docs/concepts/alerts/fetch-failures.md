---
id: fetch-failure-reporting
title: Fetch Failure Reporting
type: concept
status: active
last_verified: 2026-07-04
related:
  - README.md
  - ../../runbooks/provider-fetch-failures.md
code:
  - src/peakguard/fetcher.py
  - src/peakguard/main.py
  - src/peakguard/notifier.py
tests:
  - tests/test_fetcher.py
  - tests/test_main.py
  - tests/test_notifier.py
---

# Fetch Failure Reporting

`peakguard.fetcher` translates provider failures into `FetchError` with a classified cause:

- `RATE_LIMIT`: an HTTP 429 response was detected.
- `EMPTY_DATA`: yfinance returned no rows.
- `UNKNOWN`: any other translated provider exception.

The orchestrator catches `FetchError` per ticker, records `FetchErrorData`, and continues. The final Telegram report groups rate-limit failures separately from other failures. Its data-health section reports successful and failed fetch counts, so a partial run cannot appear fully healthy.

Invalid ticker arguments are programmer errors and raise `ValueError`; they are not converted into `FetchError`.
