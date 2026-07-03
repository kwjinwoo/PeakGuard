---
id: PROP-0001
title: Distinguish Gist Read Failure Modes
type: proposal
status: accepted
created: 2026-07-02
related:
  - ../decisions/0002-fail-closed-on-gist-read-errors.md
  - ../runbooks/gist-history-read-failures.md
  - ../roadmap.md
code:
  - src/peakguard/main.py
  - src/peakguard/gist_client.py
---

# Distinguish Gist Read Failure Modes

## Problem

Before this proposal was accepted, `_load_history_from_gist()` caught every `GistError` and returned an empty history. A missing Gist file is a valid bootstrap condition, but invalid credentials, rate limits, unavailable GitHub APIs, and malformed responses are not.

Continuing with empty history after a transient failure can trigger unnecessary provider bootstrap calls and risks replacing valid remote history later in the run.

## Evidence

- `gist_client.read_gist()` used one unclassified `GistError` for HTTP failures and missing files.
- `peakguard.main._load_history_from_gist()` did not inspect the cause.
- The log message said no history was found even when the actual cause differed.

## Candidate direction

Represent a missing Gist file distinctly from transport, authentication, rate-limit, and response-shape errors. Bootstrap only for the missing-file case; fail the run before mutation for other read failures.

## Resolution

Accepted by [ADR-0002](../decisions/0002-fail-closed-on-gist-read-errors.md):

- A missing or inaccessible Gist is distinct from a missing file inside an existing Gist.
- Retry behavior remains the responsibility of GitHub Actions.
- Malformed CSV is fatal and cannot be followed by signal evaluation or a write.
