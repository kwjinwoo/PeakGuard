# Application Package Guide

This package contains the PeakGuard application. Maintain strict responsibility boundaries and keep dependencies flowing toward plain data and pure logic rather than coupling domain code to integrations.

## Module boundaries

- `mdd_calc.py` is the domain layer. Keep calculations deterministic and free of file, environment, logging, and network access. It owns rolling-window ATH, drawdown, threshold, days-since-ATH, Z-score, bounce, and history-update rules.
- `storage.py` owns the `ClosingPrice` value object, deterministic CSV serialization/deserialization, and local synchronous file I/O. The persisted schema is exactly `ticker,date,price`; output remains human-readable, sorted, and newline-terminated.
- `config.py` validates `config/portfolio.yaml` and converts it to immutable typed configuration objects. Invalid structure or values are programmer/configuration errors and should raise native exceptions.
- `portfolio_context.py` validates the optional local PortfoTrack allocation export and converts it to immutable typed context objects. It may verify exported facts for consistency but must not take ownership of portfolio allocation calculations.
- `portfolio_action.py` owns pure allocation-guidance classification. Keep `PortfolioAction` separate from price-derived `ReviewLevel`, and do not add I/O or portfolio calculations.
- `fetcher.py` is the sole `yfinance` boundary. Fetch only data needed by the pipeline, keep calls synchronous, classify known failures, and convert external results to package value objects.
- `notifier.py` is the Telegram boundary and owns report formatting. Keep pure formatting separate from HTTP sending and retain the single consolidated daily-message behavior.
- `gist_client.py` is the GitHub Gist HTTP boundary. Production history is `peak_prices.csv`; do not reintroduce the older JSON/`peak_prices.json` design.
- `errors.py` defines expected application failures from storage and external services.
- `main.py` orchestrates the pipeline. It may compose all layers, but reusable calculations, formatting, serialization, and HTTP details belong in their respective modules.

Do not move network or filesystem operations into `mdd_calc.py`, embed business calculations in API clients, or make lower-level modules call the orchestrator.

## Behavioral invariants

- ATH means the maximum closing price in the inclusive 365-calendar-day window, not a lifetime high.
- Price history is grouped by ticker, kept in ascending date order, upserted by trading date, and trimmed to the rolling window.
- Drawdown threshold checks are inclusive.
- A failed ticker fetch must be recorded and skipped without preventing other tickers from being processed.
- Network calls require finite timeouts and must translate request/provider failures into `FetchError`, `NotificationError`, or `GistError` as appropriate.
- Missing credentials and invalid arguments remain native validation errors; do not hide them inside application errors.
- Persistence errors use `StorageError`. Do not add databases, ORMs, or asynchronous file I/O.
- Continue using `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GIST_PAT`, and `GIST_ID` from `os.environ`.

## Change expectations

- Add or update the matching `tests/test_<module>.py` before changing behavior.
- Validate edge cases such as a new rolling high, an expired high, an exact threshold match, insufficient history, malformed external data, and partial provider failure where relevant.
- Mock every external call. Never use live yfinance, Telegram, or Gist traffic in tests.
- Avoid broad `except Exception` except directly around an unpredictable third-party boundary where it is immediately translated to the correct typed error. Do not catch invariant violations merely to continue.
