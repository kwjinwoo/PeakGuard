---
id: ADR-0002
title: Fail Closed on Gist History Read Errors
type: decision
status: accepted
created: 2026-07-04
related:
  - ../proposals/PROP-0001-distinguish-gist-read-failures.md
  - ../runbooks/gist-history-read-failures.md
  - ../roadmap.md
code:
  - src/peakguard/errors.py
  - src/peakguard/gist_client.py
  - src/peakguard/main.py
tests:
  - tests/test_errors.py
  - tests/test_gist_client.py
  - tests/test_main.py
---

# ADR-0002: Fail closed on Gist history read errors

- Status: Accepted
- Date: 2026-07-04

## Context

PeakGuard previously converted every `GistError` into empty history. A missing history file is a valid first-run condition, but credentials, rate limits, network failures, invalid API responses, and malformed CSV do not prove that no history exists. Continuing after those failures could evaluate signals from incomplete data and replace valid remote history.

## Decision

`GistError` carries an explicit `GistFailureCause`. The Gist boundary distinguishes missing-file, authentication, rate-limit, network, malformed-response, malformed-history, and unknown failures.

Only a missing `peak_prices.csv` inside a successfully read existing Gist triggers automatic bootstrap. A missing or inaccessible Gist is an HTTP failure, not a missing-file condition. All other read and parse failures propagate before price fetching, report delivery, or history writes.

PeakGuard does not retry Gist operations internally. Scheduled or manually dispatched GitHub Actions reruns remain the retry boundary.

## Consequences

- A persistence incident cannot silently replace known history with a bootstrap dataset.
- Operators must correct access, service, response, or CSV failures and rerun the job.
- Adding a new configured ticker still bootstraps that ticker when valid history was loaded.
- Failure categories are part of the application error contract and require focused tests.

## Alternatives considered

- Treat Gist HTTP 404 as first run: rejected because it can also mean a wrong Gist ID, deleted Gist, or inaccessible private Gist.
- Retry in `gist_client.py`: rejected to keep the synchronous client small and avoid multiplying API calls; workflow reruns are sufficient for daily monitoring.
- Continue with read-only reporting after a failed history load: rejected because discount signals would be based on unverified persistence state.
