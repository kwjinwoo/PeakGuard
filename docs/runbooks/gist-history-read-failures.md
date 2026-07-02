---
id: runbook-gist-history-read-failures
title: Gist History Read Failures
type: runbook
status: active
related:
  - ../proposals/PROP-0001-distinguish-gist-read-failures.md
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

## Current caution

The current implementation logs every `GistError` as missing history and continues with an empty dataset. Until [PROP-0001](../proposals/PROP-0001-distinguish-gist-read-failures.md) is resolved, inspect the underlying cause before allowing a failed run to overwrite remote history.

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
