# PeakGuard

A zero-cost, serverless **Maximum Drawdown (MDD)** tracking tool.

PeakGuard monitors a 1-year rolling All-Time High (ATH) for selected tech stocks and calculates
the current drawdown. When user-defined thresholds are breached, it sends alerts via Telegram —
all powered by GitHub Actions with no server required.

---

## How It Works

### Daily Pipeline

Each run executes the following pipeline (`src/peakguard/main.py`):

1. **Load config** — Read tickers and alert thresholds from `config/portfolio.yaml`.
2. **Load history** — Read the 1-year rolling price history from `peak_prices.csv` stored in a GitHub Gist.
3. **For each ticker:**
   - **Bootstrap** (first run): Fetch the full 1-year closing price history via `yfinance` and store it.
   - **Daily update**: Fetch today's closing price, append it to history, and trim entries older than 365 days.
4. **Compute rolling ATH** — The ATH is the highest closing price within the 365-day window, not an all-time record.
5. **Evaluate and send alerts** (see alert types below).
6. **Batch fetch-error report** — If any tickers failed to fetch, send a summary alert.
7. **Persist** — Write the updated history back to the GitHub Gist as `peak_prices.csv`.

### Rolling Window ATH

ATH is calculated from the most recent 365 calendar days of closing prices, not the historical all-time record.
This means the ATH resets naturally as old data ages out of the window.

An **ATH alert** is sent whenever the rolling ATH value changes (new high reached or previous ATH aged out).

### Alert Types

| Alert | Trigger condition |
|---|---|
| **ATH** | Rolling ATH value changed (new peak or window expiry) |
| **MDD** | Drawdown from rolling ATH meets or exceeds the ticker's configured threshold |
| **Days since ATH** | Days elapsed since the rolling ATH date exceeds `days_since_ath_limit` |
| **Z-score** | Price Z-score (vs. 1-year history) falls below `zscore_threshold` |
| **Bounce from bottom** | Recovery from 1-year low meets or exceeds `bounce_from_bottom_min` |
| **Fetch errors** | One or more tickers failed to fetch (batched into a single report) |

All alerts are delivered via Telegram Bot API.

---

## Configuration

Edit `config/portfolio.yaml` to define tickers, per-ticker MDD thresholds, and global alert thresholds.

```yaml
tickers:
  NVDA:
    name: "Nvidia"
    threshold: 15.0   # MDD alert fires when drawdown >= 15%

alert_thresholds:
  days_since_ath_limit: 180     # alert if ATH not refreshed for 180+ days
  zscore_threshold: -2.0        # alert if price Z-score drops below -2.0
  bounce_from_bottom_min: 3.0   # alert if price bounces 3%+ from 1-year low
```

**Current tracked assets:**

| Ticker | Name |
|---|---|
| `AMZN` | Amazon |
| `MSFT` | Microsoft |
| `META` | Meta |
| `NVDA` | Nvidia |
| `GOOGL` | Google |

---

## Architecture

```
src/
└── peakguard/
    ├── main.py        # Pipeline orchestration
    ├── mdd_calc.py    # Pure domain logic (drawdown, Z-score, bounce, rolling ATH)
    ├── storage.py     # CSV serialization/deserialization & local file I/O
    ├── config.py      # YAML config loader
    ├── fetcher.py     # yfinance wrapper (price & history fetching)
    ├── notifier.py    # Telegram Bot API wrapper (all alert types)
    ├── gist_client.py # GitHub Gist API wrapper (remote CSV persistence)
    └── errors.py      # Custom error hierarchy
```

**Layered Design:**

- **Domain** (`mdd_calc`) — Pure business logic, no I/O or network calls
- **Storage** (`storage`) — CSV serialization, local file I/O for development/testing
- **External Services** (`fetcher`, `notifier`, `gist_client`) — All network calls, isolated with graceful error handling

---

## Persistence

Price history is stored as a CSV file (`peak_prices.csv`) in a GitHub Gist.

```
ticker,date,price
NVDA,2025-03-06,112.64
NVDA,2025-03-07,117.93
...
```

- Each row is one daily closing price per ticker.
- The window is trimmed to the last 365 days on every write.
- On first run for a new ticker, the full 1-year history is bootstrapped via `yfinance`.

---

## Requirements

- Python **3.12+**
- [uv](https://docs.astral.sh/uv/) (package manager)

---

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

### 3. Set Environment Variables

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Target chat ID for alerts |
| `GIST_PAT` | GitHub personal access token (Gist read/write scope) |
| `GIST_ID` | Target Gist ID for `peak_prices.csv` |

These are injected automatically via GitHub Actions Secrets in production.

### 4. Run

```bash
python src/main.py
```

---

## Development

### Pre-commit Hooks

```bash
pre-commit run --all-files
```

Hooks: `check-yaml`, `check-toml`, `end-of-file-fixer`, `trailing-whitespace`, **Ruff** (lint + autofix), **Black** (format).

### Testing

All external calls (`yfinance`, Telegram API, Gist API) must be mocked. Tests never hit real networks.

```bash
pytest
```

### Commit Convention

Format: `<type>(<scope>): <short summary>`

| Type | Scopes |
|---|---|
| `feat`, `fix`, `refactor`, `test`, `chore`, `docs` | `domain`, `storage`, `fetcher`, `notifier`, `ci`, `tests`, `config` |

Examples:
- `feat(domain): add rolling window ATH calculation`
- `fix(fetcher): handle yfinance rate limit exception`
- `test(notifier): mock telegram api for zscore alert`

---

## License

[Apache License 2.0](LICENSE)
