---
id: current-status
title: Current Status
type: status
status: active
last_verified: 2026-07-04
verified_by:
  - uv run pytest -q
  - uv run pre-commit run --all-files
related:
  - architecture.md
  - roadmap.md
  - work-notes/README.md
code:
  - src/peakguard
tests:
  - tests
---

# Current Status

This page is the short starting snapshot for maintainers and LLM agents. It describes verified repository state, not planned behavior.

## Baseline

- PeakGuard is a Python 3.12+ synchronous batch application.
- Production runs through `.github/workflows/mdd-check.yml` on weekdays and supports manual dispatch.
- The pipeline reads and writes `peak_prices.csv` in a GitHub Gist.
- Portfolio and alert limits are loaded from `config/portfolio.yaml`.
- Daily output is one consolidated Telegram message containing active alerts, fetch failures, and data health.
- Tests: **273 passed** on 2026-07-04.
- Pre-commit: all configured hooks passed on 2026-07-04.

## Implemented capabilities

- One-year price-history bootstrap for newly configured tickers.
- Daily close fetch and date-based history upsert.
- Inclusive 365-day rolling ATH.
- Drawdown, threshold, days-since-ATH, Z-score, and bounce calculations.
- MDD, Z-score, stale-ATH, bounce, ATH-update, and fetch-failure report formatting.
- CSV serialization and local development file I/O.
- GitHub Gist persistence and Telegram delivery.
- Graceful continuation when an individual ticker fetch fails.
- Typed Gist failure categories with fail-closed history loading; only an explicitly missing `peak_prices.csv` triggers bootstrap.
- Final price-fetch, Gist read/write, signal-evaluation, and remote-history health in every reachable daily report path.
- Health-only Telegram reporting before fatal Gist read or write errors are propagated to fail the workflow.
- Inclusive configured Z-score alerts in daily orchestration, with safe unavailable handling for insufficient or zero-variance history.
- Deterministic discount review levels derived from MDD, Z-score, and bounce, shown before supporting metrics.
- Explicit `THESIS_CHECK` precedence reserved for a future non-price asset policy input.

## Known gaps and concerns

- The README's current tracked-assets table lists only US equities while `portfolio.yaml` also contains Korean ETFs.

## Update rule

Change this page only after verifying the new state. Keep details in concepts, proposals, decisions, roadmap, or work notes and link them here rather than expanding this page indefinitely.
