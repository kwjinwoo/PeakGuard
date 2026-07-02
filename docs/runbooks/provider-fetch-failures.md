---
id: runbook-provider-fetch-failures
title: Provider Fetch Failures
type: runbook
status: active
related:
  - ../concepts/alerts/fetch-failures.md
  - ../operations.md
code:
  - src/peakguard/fetcher.py
  - src/peakguard/main.py
tests:
  - tests/test_fetcher.py
  - tests/test_main.py
---

# Provider Fetch Failures

## Symptoms

- Telegram report contains a rate-limit or other fetch-failure section.
- Workflow logs contain `Skipping <ticker>` or `Failed to fetch`.

## Checks

1. Identify whether the cause is `RATE_LIMIT`, `EMPTY_DATA`, or `UNKNOWN` in logs and report output.
2. Confirm the ticker still exists and is valid in `config/portfolio.yaml`.
3. Check whether one ticker or all tickers failed.
4. For broad failures, check yfinance/provider availability before changing code.

## Recovery

- A single transient failure requires no history repair; the ticker was skipped and other tickers continued.
- Re-run manually only when duplicate same-date updates are safe; history updates use date upsert semantics.
- For a persistent invalid ticker, correct configuration and add or update configuration tests if schema behavior changed.
- Never put live provider calls into the test suite while diagnosing.
