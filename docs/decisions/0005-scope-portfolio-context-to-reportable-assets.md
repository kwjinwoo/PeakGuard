---
id: ADR-0005
title: Scope Portfolio Context to Reportable Assets
type: decision
status: accepted
created: 2026-07-07
related:
  - ../roadmap.md
  - ../concepts/portfolio-actions.md
  - ../concepts/alerts/README.md
  - 0004-separate-price-levels-from-portfolio-actions.md
code:
  - config/portfolio.yaml
  - src/peakguard/main.py
  - src/peakguard/notifier.py
tests:
  - tests/test_main.py
  - tests/test_notifier.py
---

# ADR-0005: Scope portfolio context to reportable assets

- Status: Accepted
- Date: 2026-07-07

## Context

PortfoTrack exports portfolio-wide allocation groups, but PeakGuard is a focused
price-signal monitor rather than a portfolio dashboard. Listing every PortfoTrack
asset or allocation group would add noise, lengthen the Telegram message, and blur
ownership between the two products.

## Decision

PeakGuard reports only configured individual stocks and ETFs that are reportable in
the current run. A ticker is reportable when it has an active price signal or review
level under the existing alert rules. Fetch failures and run health remain separate
report sections.

For each reportable ticker, PeakGuard may attach only the mapped PortfoTrack group
facts needed to interpret that ticker's `PortfolioAction`. It must not enumerate:

- every asset or group in the PortfoTrack export;
- configured tickers with no active signal merely because portfolio context exists;
- unrelated cash, pension, deposit, real-estate, or other portfolio holdings; or
- a portfolio-wide allocation dashboard.

Portfolio context enriches an existing ticker alert; it never expands the report
universe. The consolidated single-message model remains in force, and portfolio
context should be compact rather than a repeated full portfolio summary.

## Consequences

- Telegram reports stay centered on actionable review triggers and remain compact.
- PortfoTrack remains the place to inspect the complete portfolio and allocation.
- Adding portfolio context cannot make an otherwise quiet ticker reportable.
- Formatter tests must prove that unalerted tickers and unrelated context groups are
  absent from the message.

## Alternatives considered

- A full PortfoTrack allocation section was rejected because it duplicates a
  portfolio tracker and obscures PeakGuard's alerting purpose.
- Reporting every configured ticker with allocation facts was rejected because a
  daily inventory is not a review trigger.
- Sending a second portfolio message was rejected because PeakGuard keeps one
  consolidated alert report and does not own portfolio-dashboard UX.
