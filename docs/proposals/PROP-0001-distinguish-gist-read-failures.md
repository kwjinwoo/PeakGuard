---
id: PROP-0001
title: Distinguish Gist Read Failure Modes
type: proposal
status: proposed
created: 2026-07-02
related:
  - ../runbooks/gist-history-read-failures.md
  - ../roadmap/now.md
code:
  - src/peakguard/main.py
  - src/peakguard/gist_client.py
---

# Distinguish Gist Read Failure Modes

## Problem

`_load_history_from_gist()` catches every `GistError` and returns an empty history. A missing Gist file is a valid bootstrap condition, but invalid credentials, rate limits, unavailable GitHub APIs, and malformed responses are not.

Continuing with empty history after a transient failure can trigger unnecessary provider bootstrap calls and risks replacing valid remote history later in the run.

## Evidence

- `gist_client.read_gist()` currently uses one `GistError` type for HTTP failures and missing files.
- `peakguard.main._load_history_from_gist()` does not inspect the cause.
- The existing log message says no history was found even when the actual cause may differ.

## Candidate direction

Represent a missing Gist file distinctly from transport, authentication, rate-limit, and response-shape errors. Bootstrap only for the missing-file case; fail the run before mutation for other read failures.

## Open questions

- Should a missing target Gist be distinct from a missing file inside an existing Gist?
- Should retry behavior remain the responsibility of GitHub Actions or be implemented in the HTTP client?
- Should malformed CSV be treated as a fatal persistence error without attempting a write?
