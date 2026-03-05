# PeakGuard

A zero-cost, serverless **Maximum Drawdown (MDD)** tracking tool.

PeakGuard monitors All-Time High (ATH) prices and calculates the current drawdown for selected assets.
When a user-defined threshold is breached, it sends an alert via Telegram — all powered by GitHub Actions with no server required.

---

## Features

- **Zero-cost operation** — Runs entirely on GitHub Actions (cron schedule), no cloud instances needed
- **ATH & MDD tracking** — Automatically tracks All-Time High and calculates Maximum Drawdown
- **Telegram alerts** — Sends notifications when drawdown exceeds configured thresholds
- **Gist-based persistence** — Stores peak prices in `peak_prices.json` via GitHub Gist (no database, no repo commits for data)
- **Daily post-market check** — Fetches closing prices once a day via `yfinance`

## Target Assets

| Category | Assets |
|---|---|
| Index ETFs | S&P 500, NASDAQ |
| Tech Stocks | Amazon, Microsoft, Meta, Nvidia, Google |

## Architecture

```
src/
├── main.py          # Entry point
├── mdd_calc.py      # Pure domain logic (drawdown calculation)
├── storage.py       # JSON serialization/deserialization & local file I/O
├── gist_client.py   # GitHub Gist API wrapper (remote persistence)
├── fetcher.py       # yfinance wrapper (current price fetching)
└── notifier.py      # Telegram Bot API wrapper (alerts)
```

**Layered Design** — Strict separation of concerns:

- **Domain** (`mdd_calc`) — Pure business logic, no I/O
- **Storage** (`storage`) — JSON serialization/deserialization, local file I/O
- **External Services** (`fetcher`, `notifier`, `gist_client`) — Network calls with graceful error handling

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) (package manager)

## Getting Started

### 1. Clone & Setup

```bash
git clone https://github.com/<your-username>/PeakGuard.git
cd PeakGuard
uv sync
```

### 2. Install Pre-commit Hooks

```bash
pre-commit install
```

### 3. Configure Portfolio

Edit `config/portfolio.yaml` to define your target tickers and alert thresholds.

### 4. Set Environment Variables

Set the following secrets (used by GitHub Actions):

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Target chat ID for alerts |
| `GITHUB_TOKEN` | GitHub personal access token (Gist read/write) |
| `GIST_ID` | Target Gist ID for `peak_prices.json` |

### 5. Run

```bash
python src/main.py
```

## Development

### Pre-commit Hooks

This project uses the following pre-commit hooks:

- **pre-commit-hooks** — `check-yaml`, `check-toml`, `end-of-file-fixer`, `trailing-whitespace`
- **Ruff** — Linting with auto-fix
- **Black** — Code formatting

```bash
pre-commit run --all-files
```

### Testing

Tests use `pytest`. All external calls (`yfinance`, Telegram API) must be mocked.

```bash
pytest
```

### Commit Convention

This project follows **Conventional Commits** with a required scope:

```
<type>(<scope>): <short summary>
```

| Type | Scopes |
|---|---|
| `feat`, `fix`, `refactor`, `test`, `chore`, `docs` | `domain`, `storage`, `fetcher`, `notifier`, `ci`, `tests`, `config` |

Examples:
- `feat(domain): add MDD calculation logic`
- `fix(fetcher): handle yfinance rate limit exception`

## License

[Apache License 2.0](LICENSE)
