---
id: operations
title: Operations
type: operations
status: active
last_verified: 2026-07-02
related:
  - architecture.md
  - runbooks/README.md
  - concepts/data-contracts.md
code:
  - .github/workflows/mdd-check.yml
  - src/peakguard/main.py
  - src/peakguard/gist_client.py
  - src/peakguard/notifier.py
---

# Operations

PeakGuard runs from `.github/workflows/mdd-check.yml` using `python src/main.py`. The workflow can also be started manually with `workflow_dispatch`.

## Required secrets

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Authorizes the Telegram Bot API request |
| `TELEGRAM_CHAT_ID` | Selects the report destination |
| `GIST_PAT` | Authorizes GitHub Gist reads and writes |
| `GIST_ID` | Selects the Gist containing `peak_prices.csv` |

Secrets are supplied through environment variables. They must not appear in configuration, logs, fixtures, documentation examples, or committed files.

## Persistence

Production history is a human-readable Gist file named `peak_prices.csv` with the header:

```csv
ticker,date,price
```

Rows are sorted by ticker and date. Local storage functions exist for development and testing, but the production pipeline reads and writes through `peakguard.gist_client`.

## Failure behavior

- One ticker fetch failure is collected and processing continues with other tickers.
- Telegram request failures are logged and do not prevent the final history-save attempt.
- Missing required environment variables are fatal validation errors.
- Network requests use finite timeouts and typed integration errors.
- Treat malformed persisted data as an operational incident; do not silently invent replacement history without confirming intended recovery behavior.
- Bootstrap automatically only when `peak_prices.csv` is absent from an otherwise valid Gist response. All other Gist read or history-parse failures stop the run before evaluation and remote writes.

## Local commands

```bash
uv sync
uv run pytest
uv run pre-commit run --all-files
```

Running `python src/main.py` performs real provider, Telegram, and Gist operations and therefore requires deliberate credential setup. Unit tests must always mock those boundaries.
