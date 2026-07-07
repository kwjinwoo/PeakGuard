---
id: system-architecture
title: System Overview
type: architecture
status: active
last_verified: 2026-07-07
related:
  - concepts/domain-model.md
  - operations.md
  - decisions/0001-csv-gist-persistence.md
  - decisions/0005-scope-portfolio-context-to-reportable-assets.md
code:
  - src/peakguard/main.py
  - src/peakguard/portfolio_action.py
  - src/peakguard/portfolio_context.py
tests:
  - tests/test_main.py
  - tests/test_portfolio_action.py
  - tests/test_portfolio_context.py
---

# System Overview

PeakGuard is a synchronous Python 3.12+ batch application. GitHub Actions starts it once per configured weekday; it has no continuously running server.

## Daily data flow

1. `src/main.py` starts `peakguard.main.run()`.
2. `peakguard.config` loads assets and alert limits from `config/portfolio.yaml`.
3. `peakguard.portfolio_context` optionally loads and classifies the local PortfoTrack export; invalid existing context fails before external calls.
4. `peakguard.gist_client` reads `peak_prices.csv` from a GitHub Gist.
5. For each ticker, `peakguard.fetcher` obtains either one year of bootstrap history or the latest close from yfinance.
6. `peakguard.mdd_calc` updates the rolling history and calculates metrics without performing I/O.
7. `peakguard.main` resolves mapped allocation groups and derives portfolio actions without changing which tickers are reportable.
8. `peakguard.storage` serializes updated history, and `peakguard.gist_client` writes it back to the Gist.
9. `peakguard.notifier` formats active alerts, fetch failures, and final data health into one Telegram report and sends it.

Fatal Gist reads skip price evaluation and writes but still attempt a health-only report before the error fails the workflow. Gist writes happen before notification so the report describes the actual persistence outcome.

## Boundaries

| Area | Module | Responsibility |
| --- | --- | --- |
| Orchestration | `peakguard.main` | Coordinates the daily pipeline and partial failures |
| Domain | `peakguard.mdd_calc` | Pure calculations and rolling-history rules |
| Portfolio policy | `peakguard.portfolio_action` | Pure allocation-action classification separate from price levels |
| Configuration | `peakguard.config` | YAML parsing and validation |
| Portfolio context | `peakguard.portfolio_context` | Optional PortfoTrack schema 1.0 JSON validation and immutable context objects |
| Storage format | `peakguard.storage` | `ClosingPrice`, CSV conversion, local file I/O |
| Market data | `peakguard.fetcher` | yfinance integration |
| Notification | `peakguard.notifier` | Telegram formatting and HTTP integration |
| Remote persistence | `peakguard.gist_client` | GitHub Gist HTTP integration |
| Error taxonomy | `peakguard.errors` | Expected I/O and provider failure types |

Domain code must remain deterministic and unaware of files, environment variables, HTTP, yfinance, Telegram, or Gists. Integration modules translate provider failures into typed application errors. The orchestrator decides whether a failure is recoverable for the current run.

The PortfoTrack context boundary is a local, read-only loader connected before remote
I/O. Orchestration classifies freshness, resolves only configured group mappings,
and derives portfolio actions. Telegram renders compact allocation facts only for
already-reportable tickers and emits a stale warning once per report. PortfoTrack
remains responsible for all allocation calculations and full-portfolio presentation.

## Design constraints

- Zero-cost serverless operation through GitHub Actions.
- One post-market batch run; no real-time or high-frequency processing.
- Synchronous network and file I/O with finite timeouts.
- CSV-in-Gist persistence; no database or ORM.
- One consolidated Telegram report rather than one message per ticker.
- Portfolio context enriches only configured individual stocks and ETFs already made
  reportable by price signals; it never produces a full portfolio inventory.
- Partial ticker fetch failures do not stop processing other tickers.
- Fatal persistence failures are reported when Telegram remains available and then propagated.

See [Domain model](concepts/domain-model.md), [Operations](operations.md), and [ADR-0001](decisions/0001-csv-gist-persistence.md).
