---
id: system-architecture
title: System Overview
type: architecture
status: active
last_verified: 2026-07-02
related:
  - concepts/domain-model.md
  - operations.md
  - decisions/0001-csv-gist-persistence.md
code:
  - src/peakguard/main.py
tests:
  - tests/test_main.py
---

# System Overview

PeakGuard is a synchronous Python 3.12+ batch application. GitHub Actions starts it once per configured weekday; it has no continuously running server.

## Daily data flow

1. `src/main.py` starts `peakguard.main.run()`.
2. `peakguard.config` loads assets and alert limits from `config/portfolio.yaml`.
3. `peakguard.gist_client` reads `peak_prices.csv` from a GitHub Gist.
4. For each ticker, `peakguard.fetcher` obtains either one year of bootstrap history or the latest close from yfinance.
5. `peakguard.mdd_calc` updates the rolling history and calculates metrics without performing I/O.
6. `peakguard.notifier` formats active alerts and fetch failures into one Telegram report and sends it.
7. `peakguard.storage` serializes updated history, and `peakguard.gist_client` writes it back to the Gist.

## Boundaries

| Area | Module | Responsibility |
| --- | --- | --- |
| Orchestration | `peakguard.main` | Coordinates the daily pipeline and partial failures |
| Domain | `peakguard.mdd_calc` | Pure calculations and rolling-history rules |
| Configuration | `peakguard.config` | YAML parsing and validation |
| Storage format | `peakguard.storage` | `ClosingPrice`, CSV conversion, local file I/O |
| Market data | `peakguard.fetcher` | yfinance integration |
| Notification | `peakguard.notifier` | Telegram formatting and HTTP integration |
| Remote persistence | `peakguard.gist_client` | GitHub Gist HTTP integration |
| Error taxonomy | `peakguard.errors` | Expected I/O and provider failure types |

Domain code must remain deterministic and unaware of files, environment variables, HTTP, yfinance, Telegram, or Gists. Integration modules translate provider failures into typed application errors. The orchestrator decides whether a failure is recoverable for the current run.

## Design constraints

- Zero-cost serverless operation through GitHub Actions.
- One post-market batch run; no real-time or high-frequency processing.
- Synchronous network and file I/O with finite timeouts.
- CSV-in-Gist persistence; no database or ORM.
- One consolidated Telegram report rather than one message per ticker.
- Partial ticker fetch failures do not stop processing other tickers.

See [Domain model](concepts/domain-model.md), [Operations](operations.md), and [ADR-0001](decisions/0001-csv-gist-persistence.md).
