---
id: current-status
title: Current Status
type: status
status: active
last_verified: 2026-07-21
verified_by:
  - uv run pytest -q
  - uv run python .agents/skills/peakguard-wiki/scripts/validate_wiki.py
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
- PortfoTrack context does not expand the report universe: quiet configured tickers
  and unrelated portfolio groups remain omitted.
- Tests: **371 passed** on 2026-07-21.
- Wiki validation: **40 documents passed** on 2026-07-21.
- Pre-commit: all configured hooks passed on 2026-07-21.

## Implemented capabilities

- Local `peakguard assets list/add/update/remove` commands for tracked-asset management.
  Mutations reject duplicate or unknown tickers, require removal confirmation,
  validate the complete generated configuration, and replace it atomically without
  making network calls.
- Manual `peakguard history prune` preview and apply workflow for remote rows that no
  longer belong to tracked tickers. Active tickers are protected, scheduled runs do
  not prune, and batch application requires a second confirmation.
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
- Deterministic discount review levels derived from MDD, Z-score, and bounce, used
  with portfolio actions to prioritize report sections.
- Explicit `THESIS_CHECK` precedence reserved for a future non-price asset policy input.
- Backward-compatible optional asset metadata with validated asset types, portfolio
  groups, thesis policy, and one-way canonical US-exposure proxy mappings. The two
  KRW wrapper ETFs map to `SPY` and `QQQ` while retaining their own price feeds.
- Asset-aware Telegram review prompts for individual stocks, core ETFs, bond ETFs,
  and gold proxies, while legacy untyped entries retain price-only reporting.
- Optional immutable loading and strict validation of PortfoTrack's schema 1.0 local
  allocation export before external calls. Missing context preserves price-only mode;
  age 0–7 days is current, 8–30 days is stale, and 31+ days expires allocation use.
- Optional GitHub Actions secret transport restores PortfoTrack context with
  restrictive file permissions without committing or logging portfolio amounts.
- Pure `PortfolioAction` classification remains separate from `ReviewLevel`, with
  above-range `NO_ADD` precedence and table-tested ETF, thesis, and watch policies;
  current or stale PortfoTrack groups are now resolved during daily orchestration
  and the resulting allocation facts and action reach `TickerSummary`. Missing,
  unknown, and expired mappings preserve price-only behavior.
- Reportable configured stocks and ETFs are grouped into `Action Review`, `Watch
  Only`, and optional `No Action` sections. Recovery-only signals use one compact
  line; focused entries keep price, allocation, and suggested review visually
  separate. Healthy data status uses one line, while partial or failed runs show
  details. Stale context reports its exact snapshot date and age. Quiet tickers and
  unrelated context groups stay omitted, and a worst-case seven-ticker formatting
  test protects Telegram's 4,096-character limit.
- Formatting tests protect non-prescriptive language for every portfolio action and
  preserve the three-section order. The accepted presentation contract is recorded
  in ADR-0006.

## Update rule

Change this page only after verifying the new state. Keep details in concepts, proposals, decisions, roadmap, or work notes and link them here rather than expanding this page indefinitely.
