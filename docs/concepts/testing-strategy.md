---
id: testing-strategy
title: Testing Strategy
type: concept
status: active
last_verified: 2026-07-02
related:
  - domain-model.md
  - alerts/README.md
code:
  - tests
tests:
  - tests
---

# Testing Strategy

PeakGuard uses pytest and follows red → green → refactor for behavioral changes.

## Boundaries

- Domain tests use fixed values and dates and exercise pure functions directly.
- Storage tests verify validation, deterministic CSV output, round trips, and local I/O with `tmp_path`.
- Integration-module tests mock yfinance or `requests` at the symbol used by the module under test.
- Orchestrator tests mock config, persistence, provider, and notifier collaborators.
- Tests never contact yfinance, Telegram, or GitHub Gist.

## Required behavioral coverage

- Happy path and relevant validation failures.
- Exact inclusive threshold boundary.
- New rolling high and expired data-window behavior.
- Partial ticker fetch failure without aborting remaining work.
- External timeout, HTTP error, empty data, and malformed persisted content where applicable.

Commands:

```bash
uv run pytest
uv run pre-commit run --all-files
```

See `tests/AGENTS.md` for agent-specific implementation rules.
