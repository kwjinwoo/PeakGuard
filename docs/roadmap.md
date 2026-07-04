---
id: product-roadmap
title: Product Roadmap
type: roadmap
status: active
related:
  - status.md
  - proposals/PROP-0001-distinguish-gist-read-failures.md
  - proposals/PROP-0003-portfotrack-context-mvp.md
  - concepts/alerts/README.md
  - decisions/README.md
---

# Product Roadmap

PeakGuard will evolve from a price-drawdown notifier into a portfolio-aware review trigger for ETFs and individual stocks. This is the single source of truth for planned outcomes and their completion state.

## Product direction

PeakGuard must not act as an automatic buy or sell signal generator.

```text
PeakGuard = discount and risk signal detector
PortfoTrack = allocation and rebalancing controller
Investment thesis review = final decision gate
```

The operating principle is:

```text
Price became attractive -> review the asset
Portfolio room exists -> consider allocation
Thesis remains valid -> decide manually
```

The user-facing framing is always: **Review trigger, not buy signal.**

For verified current behavior and known gaps, see [Current status](status.md). Detailed designs that are not yet accepted belong in [Proposals](proposals/README.md), not in this checklist.

## Progress overview

| Phase | Theme | State | Main outcome |
| ---: | --- | --- | --- |
| 1 | Reliability and data safety | Complete | Never evaluate signals from invalid persistence state |
| 2 | Discount signal model | Complete | Convert raw metrics into investment-review levels |
| 3 | Asset taxonomy | Planned | Apply different rules to stocks, ETFs, bonds, and gold |
| 4 | Portfolio-aware alerts | Planned | Combine price signals with PortfoTrack allocation state |
| 5 | Reporting and UX | Planned | Produce concise, non-prescriptive review prompts |
| 6 | Maintenance and documentation | Ongoing | Keep behavior understandable to humans and LLM agents |

A checkbox is complete only when implementation, tests, and affected documentation are all finished. Update [Current status](status.md) only after verification.

## Phase 1 — Reliability and data safety

Objective: ensure PeakGuard never silently treats operational failures as valid investment data.

### Gist failure semantics

- [x] Introduce explicit missing-file, authentication, rate-limit, network, parse, and unknown Gist failure categories.
- [x] Treat a missing `peak_prices.csv` as the only automatic bootstrap case.
- [x] Abort signal evaluation on authentication, rate-limit, network, or malformed-history failures.
- [x] Prevent remote history writes after a failed history read.
- [x] Cover every failure category with focused tests.

Related design: [PROP-0001](proposals/PROP-0001-distinguish-gist-read-failures.md).

### Explicit history-load behavior

- [x] Define behavior for a missing file, empty valid file, malformed CSV, and unavailable Gist.
- [x] Stop `_load_history_from_gist()` from treating every `GistError` as first run.
- [x] Distinguish ticker fetch failures from fatal persistence failures in orchestration.
- [x] Ensure a fatal history-load failure cannot produce discount alerts.

### Data-health reporting

- [x] Add minimal price-fetch, Gist-read, and Gist-write health to the daily report.
- [x] Report partial ticker fetch success without presenting it as a fully healthy run.
- [x] Explain when no price signals were evaluated and remote history was not modified.
- [x] Test healthy, partial-fetch, and fatal-persistence report paths.

### Completion criteria

- [x] Only an explicitly missing history file can trigger bootstrap.
- [x] Operational failures fail safely without replacing valid history.
- [x] Users can distinguish data-health failures from asset-price signals.

## Phase 2 — Discount signal model

Objective: move from independent alert booleans to a clear investment-review model.

### Z-score integration

- [x] Add Z-score to `TickerSummary` and daily orchestration.
- [x] Evaluate the configured `zscore_threshold`.
- [x] Include Z-score in Telegram report entries.
- [x] Connect domain Z-score tests to orchestration and notifier tests.

### Discount levels

- [x] Define domain-level review states such as `NONE`, `WATCH`, `ATTRACTIVE`, `DEEP_DISCOUNT`, `THESIS_CHECK`, and `RECOVERY_WATCH`.
- [x] Derive the level from MDD, Z-score, and bounce inputs.
- [x] Preserve existing MDD threshold behavior during migration.
- [x] Make `THESIS_CHECK` override ordinary discount language.
- [x] Show the review level before raw metrics in reports.

### Combined interpretation

- [x] Treat high MDD with ordinary Z-score as a drawdown that may be normal for the asset.
- [x] Treat high MDD with low Z-score as a stronger review trigger.
- [x] Detect statistically weak prices even when ATH drawdown is limited.
- [x] Document and test the exact level boundaries before enabling them in production.

### Completion criteria

- [x] Reports expose both MDD and Z-score context.
- [x] Review levels replace ambiguous collections of alert flags.
- [x] Report language remains a prompt for review rather than investment advice.

## Phase 3 — Asset taxonomy

Objective: stop treating every ticker as the same kind of asset.

### Asset-centric configuration

- [x] Preserve the existing `tickers` mapping and extend entries with optional asset metadata.
- [x] Add `asset_type`, `portfolio_group`, and `thesis_required` without breaking price-only configurations.
- [x] Support `proxy_for` when a tracked market symbol represents a held asset.
- [x] Validate optional field types, enum values, and incompatible combinations clearly.

### MVP asset types

- [x] Define `individual_stock`, `core_etf`, `bond_etf`, and `gold_proxy`.
- [x] Configure individual stocks with explicit thesis policy where appropriate.
- [x] Keep existing per-ticker MDD thresholds and the global Z-score threshold for the MVP.
- [x] Test legacy entries, optional metadata, proxy mappings, and invalid combinations.
- [ ] Use asset-appropriate report language.

Type-specific threshold inheritance and a full `tickers`-to-`assets` migration are deferred until the MVP proves they are necessary.

### Completion criteria

- [ ] Configured metadata describes asset meaning while legacy ticker-only entries remain valid.
- [ ] Stocks, ETFs, bonds, and gold can receive different review language.
- [ ] README examples and configured assets describe the same monitored universe.

## Phase 4 — Portfolio-aware alerts

Objective: combine PeakGuard price signals with PortfoTrack allocation context while keeping PeakGuard usable on its own.

### PortfoTrack boundary

- [ ] Define `schema_version: 1` for a read-only JSON snapshot containing `as_of`, currency, total assets, and asset-class weights and bounds.
- [ ] Load optional `config/portfotrack_context.json` into immutable validated objects.
- [ ] Keep PeakGuard functional when no portfolio snapshot is supplied.
- [ ] Fail clearly when an existing snapshot is malformed, unsupported, or internally inconsistent.
- [ ] Treat context age 0–7 days as current and 8–30 days as stale with a warning.
- [ ] Disable allocation guidance at 31 or more days old while preserving price-only alerts.
- [ ] Keep portfolio calculation ownership in PortfoTrack rather than duplicating it in PeakGuard.

### Mapping and classification

- [ ] Resolve optional ticker and proxy mappings to PortfoTrack asset-class names.
- [ ] Preserve price-only behavior for missing mappings and unknown groups.
- [ ] Keep price-derived `ReviewLevel` separate from portfolio-derived `PortfolioAction`.
- [ ] Classify below-range ETF proxies as `REBALANCE_CANDIDATE` and other discounted assets as `ACTION_REVIEW`.
- [ ] Classify within-range discounted assets as `WATCH`.
- [ ] Classify above-range assets as `NO_ADD`, overriding attractive-price wording.
- [ ] Classify deep-discount individual stocks with explicit thesis policy as `THESIS_CHECK`.

Approximate available-room and rebalance-amount calculations are deferred; PeakGuard reports PortfoTrack allocation facts without becoming a rebalancing engine.

### Reporting and tests

- [ ] Show portfolio group, current weight, target range, status, action, and stale warning separately from price metrics.
- [ ] Use thesis language for individual stocks and rebalance language for ETF proxies.
- [ ] Test valid, missing, malformed, unsupported-version, unknown-group, and stale context paths.
- [ ] Test `below_range`, `within_range`, and `above_range` action classification.
- [ ] Keep all provider, Telegram, and Gist calls mocked.

### Completion criteria

- [ ] Price attractiveness and allocation room are shown as separate facts.
- [ ] Allocation guardrails override attractive-price wording.
- [ ] Deep-discount individual-stock prompts with thesis policy require thesis review.
- [ ] ETF prompts use rebalance-oriented language.

## Phase 5 — Reporting and UX

Objective: make Telegram reports concise, useful on mobile, and difficult to mistake for automated investment instructions.

### Report structure

- [ ] Group entries into `Action Review`, `Watch Only`, and optional `No Action` sections.
- [ ] Keep price signal, portfolio context, and suggested review visually separate.
- [x] Add a compact data-health section.
- [ ] Keep the consolidated single-message delivery model.

### Language policy

- [ ] Avoid `buy now`, `strong buy`, `sell`, `exit`, `must add`, and equivalent prescriptive wording.
- [ ] Prefer `review`, `check thesis`, `consider in next rebalance`, `watch only`, `no action`, and `allocation guardrail active`.
- [ ] Use thesis language for stocks, rebalance language for ETFs, duration-risk language for bond ETFs, and hedge-allocation language for gold.
- [ ] Add formatting tests that protect the language policy.

### Completion criteria

- [ ] Reports lead with the review level and retain supporting raw metrics.
- [ ] No report line reads as automatic trading advice.
- [ ] Reports remain readable in a mobile Telegram client.

## Phase 6 — Maintenance and documentation

Objective: keep PeakGuard easy to understand and change for humans and LLM agents.

- [x] Establish the `docs/` LLM Wiki with structured frontmatter and a canonical index.
- [x] Add a repository-local `$peakguard-wiki` read/write and validation skill.
- [x] Keep `status.md` as a short verified snapshot rather than a second roadmap.
- [ ] Update the root README to describe PeakGuard as a price-discount and portfolio-review monitor when that behavior is implemented.
- [ ] Add or update decision records as product constraints become accepted.
- [ ] Keep README, configuration examples, concepts, and current behavior aligned after every phase.
- [ ] Update roadmap checkboxes and status only after tests and pre-commit pass.

### Completion criteria

- [ ] A new maintainer can understand product intent without reading every source file.
- [ ] Wiki validation detects broken metadata, links, paths, and index coverage.
- [ ] Completed phases have verification evidence in status or linked decisions.

## Non-goals

PeakGuard will not become:

- an automated trading bot;
- a valuation engine;
- a full portfolio tracker;
- a broker integration layer;
- a replacement for investment-thesis review; or
- a real-time intraday trading system.

PeakGuard will remain serverless, low-cost or zero-cost, daily batch-oriented, testable, explicit about uncertainty, and simple enough to reason about.

## Target outcome

The final report should make the reasoning chain visible without deciding for the user:

```text
Action Review

NVDA — Deep Discount
- Drawdown from 1Y rolling ATH: -31.4%
- Z-score: -2.1
- Portfolio group: US Equity
- Current group weight: 14.8%
- Target range: 14.0–18.0%

Suggested review:
- Check thesis before adding.
- Do not exceed individual-stock allocation.

Data Health
- Fetch: all assets succeeded
- Gist read/write: succeeded
```

The intended outcome is to detect when an asset is meaningfully discounted and help determine whether it deserves review within the user's portfolio rules.
