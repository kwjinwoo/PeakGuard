---
id: ADR-0007
title: Require Explicit Manual History Pruning
type: decision
status: accepted
created: 2026-07-21
related:
  - ../operations.md
  - ../concepts/configuration.md
  - 0001-csv-gist-persistence.md
code:
  - src/peakguard/cli.py
  - src/peakguard/gist_client.py
  - src/peakguard/storage.py
tests:
  - tests/test_cli.py
---

# ADR-0007: Require explicit manual history pruning

- Status: Accepted
- Date: 2026-07-21

## Context

Removing a ticker from `config/portfolio.yaml` stops future monitoring but leaves its
existing rows in `peak_prices.csv`. Automatically deleting those rows during the next
scheduled run would turn a temporary or accidental configuration change into an
irreversible remote-data mutation.

History is small and inexpensive, while configuration changes and Gist writes cannot
be committed atomically. Immediate automatic cleanup therefore provides little
benefit relative to its recovery risk.

## Decision

Scheduled GitHub Actions runs do not prune history. Remote cleanup is a separate,
manual CLI operation:

```bash
uv run peakguard history prune
uv run peakguard history prune --ticker AMZN --apply
```

The command is a dry run unless `--apply` is supplied. It refuses to prune any ticker
still present in the current configuration. Selecting a ticker explicitly plus
`--apply` is sufficient authorization for that ticker. Applying all untracked
candidates requires an interactive confirmation or the additional `--yes` flag.

Before mutation, the command displays every candidate's row count and date range. It
uses the canonical Gist client and CSV parser/serializer, and it writes only after
the complete remote history parses successfully.

## Consequences

- Accidental or temporary ticker removal does not erase history automatically.
- Operators can inspect the exact deletion scope before any Gist write.
- Non-interactive batch cleanup remains possible but requires both `--apply` and
  `--yes`.
- Removing an asset and pruning its history are intentionally separate operations.

## Alternatives considered

- Automatic pruning in the weekday workflow was rejected because a bad configuration
  commit could delete recoverable history without a second decision.
- Pruning inside `assets remove` was rejected because local configuration replacement
  and remote Gist mutation cannot be made atomic.
- Keeping all removed history forever remains valid; pruning is optional.
