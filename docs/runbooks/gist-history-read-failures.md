---
id: runbook-gist-history-read-failures
title: Gist History Read Failures
type: runbook
status: active
related:
  - ../proposals/PROP-0001-distinguish-gist-read-failures.md
  - ../decisions/0002-fail-closed-on-gist-read-errors.md
  - ../decisions/0001-csv-gist-persistence.md
  - ../operations.md
code:
  - src/peakguard/gist_client.py
  - src/peakguard/main.py
tests:
  - tests/test_gist_client.py
  - tests/test_main.py
---

# Gist History Read Failures

## Runtime behavior

PeakGuard bootstraps automatically only when a successfully read Gist does not contain `peak_prices.csv`. Authentication, rate-limit, network, malformed-response, malformed-history, and unknown failures stop the run before price evaluation, Telegram delivery, or Gist writes. See [ADR-0002](../decisions/0002-fail-closed-on-gist-read-errors.md).

## Checks

1. Preserve the existing Gist content before manual recovery.
2. Verify `GIST_ID` points to the intended Gist without printing the secret value in logs.
3. Verify the token has Gist access and has not expired.
4. Confirm the file is named `peak_prices.csv`.
5. Confirm the header is exactly `ticker,date,price` and rows contain ISO dates and positive numeric prices.
6. Distinguish a missing file from authentication, rate-limit, network, and malformed-data failures.

## Recovery

- For a missing file on a deliberate first run, allow bootstrap to create history.
- For credential or transient API failures, restore access and rerun without replacing the preserved history.
- For malformed CSV, repair a copy, validate it with `deserialize_history()`, and retain the original for diagnosis before writing changes.
