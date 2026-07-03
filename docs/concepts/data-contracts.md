---
id: data-contracts
title: Data Contracts
type: concept
status: active
last_verified: 2026-07-04
related:
  - domain-model.md
  - configuration.md
  - ../decisions/0001-csv-gist-persistence.md
code:
  - src/peakguard/storage.py
  - src/peakguard/fetcher.py
  - src/peakguard/notifier.py
tests:
  - tests/test_storage.py
  - tests/test_main.py
  - tests/test_notifier.py
---

# Data Contracts

This page records durable formats exchanged between PeakGuard components. Provider-specific raw responses remain encapsulated by integration modules.

## Persisted price history

Gist filename: `peak_prices.csv`

```csv
ticker,date,price
NVDA,2026-07-01,157.75
```

Invariants:

- Header is exactly `ticker,date,price`.
- Dates use ISO `YYYY-MM-DD` format.
- Prices are positive numeric values.
- Output is sorted by ticker and then date.
- Output ends with a newline.
- Deserialized records are grouped by ticker and sorted ascending by date.

The canonical serializer is `src/peakguard/storage.py`.

## Configuration objects

- `TickerConfig`: ticker, display name, MDD threshold, and currency.
- `AlertThresholds`: days-since-ATH limit, negative Z-score threshold, and minimum bounce percentage.

Both are immutable. Invalid configuration raises native validation errors.

## Provider result

`PriceResult` contains a ticker, positive latest close, and provider trading date. Historical provider data is converted into `ClosingPrice` values before leaving `peakguard.fetcher`.

## Daily report input

`TickerSummary` aggregates calculated values, alert flags, and the leading `ReviewLevel` for one ticker, including an optional Z-score and its threshold result. `FetchErrorData` represents a skipped ticker fetch. `RunHealth` records fetch counts, Gist read/write status, whether signals were evaluated, and whether remote history was updated. `peakguard.notifier` converts these values to one plain-text Telegram message.

See [Configuration](configuration.md), [Domain model](domain-model.md), and [ADR-0001](../decisions/0001-csv-gist-persistence.md).
