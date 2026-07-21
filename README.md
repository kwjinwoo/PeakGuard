# PeakGuard

A zero-cost, serverless **price-discount and portfolio-review monitor**.

Project architecture, domain semantics, operations, and design decisions are documented in the [PeakGuard Wiki](docs/README.md).

PeakGuard monitors a 365-day rolling high, drawdown, statistical price weakness,
recovery, and optional PortfoTrack allocation context for configured US stocks and
US-market-exposure ETFs. Once per weekday it sends one prioritized Telegram report
through GitHub Actions. It is a review trigger, not an automated trading signal.

Optional PortfoTrack context enriches alerts only for configured individual stocks
and ETFs that already have an active signal. PeakGuard does not list the complete
PortfoTrack portfolio or turn quiet assets into report entries. Each eligible alert
uses compact allocation context, with one shared warning that identifies the exact
snapshot date and age when the data is stale.

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
5. **Evaluate review state** — Combine price signals into a review level and, when
   usable, derive a separate portfolio action.
6. **Persist** — Write the updated history back to the GitHub Gist as `peak_prices.csv`.
7. **Send one report** — Include prioritized ticker reviews, batched fetch failures,
   and final data health in one Telegram message.

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

### Report Priorities

Every reportable ticker appears in exactly one section:

| Section | Meaning |
|---|---|
| **Action Review · 집중 검토** | Review the thesis, allocation room, or next rebalance |
| **Watch Only · 관찰** | Observe a within-range asset, recovery, or informational signal |
| **No Action · 행동 보류** | Allocation upper guardrail is active; retain the alert without suggesting action |

Recovery-only entries use one compact line. Fully healthy data status also uses one
line; partial or failed runs show detailed health. Report wording is deliberately
non-prescriptive and never issues an automatic trading instruction.

---

## Configuration

Tracked assets can be managed with the CLI described below. Global alert thresholds
remain in `config/portfolio.yaml`.

```yaml
tickers:
  NVDA:
    name: "Nvidia"
    threshold: 15.0   # MDD alert fires when drawdown >= 15%
    asset_type: individual_stock
    portfolio_group: us_equity
    thesis_required: true

alert_thresholds:
  days_since_ath_limit: 180     # alert if ATH not refreshed for 180+ days
  zscore_threshold: -2.0        # alert if price Z-score drops below -2.0
  bounce_from_bottom_min: 3.0   # alert if price bounces 3%+ from 1-year low
```

### Tracked Asset CLI

Run these commands from the project root. `uv sync` installs the local `peakguard`
command; `uv run` also ensures the project environment is current before execution.

#### List tracked assets

```bash
uv run peakguard assets list
```

The table shows ticker, display name, asset type, MDD threshold, and PortfoTrack
group. Listing is read-only and performs no market or network request.

#### Add an individual stock

Only `--name` is required. The remaining defaults match PeakGuard's current US-stock
policy: 15% MDD threshold, USD, `individual_stock`, and `us_equity`.

```bash
uv run peakguard assets add AAPL --name "Apple"
```

To enable explicit thesis review for deep-discount portfolio guidance:

```bash
uv run peakguard assets add AAPL \
  --name "Apple" \
  --threshold 12.5 \
  --asset-type individual_stock \
  --portfolio-group us_equity \
  --thesis-required
```

Available add options:

| Option | Default | Meaning |
|---|---|---|
| `--name TEXT` | Required | Human-readable name shown in reports |
| `--threshold PERCENT` | `15.0` | MDD alert threshold in `(0, 100]` |
| `--currency CODE` | `USD` | Report price currency; `KRW` uses won formatting |
| `--asset-type TYPE` | `individual_stock` | `individual_stock`, `core_etf`, `bond_etf`, or `gold_proxy` |
| `--portfolio-group ID` | `us_equity` | Stable PortfoTrack `asset_id` |
| `--thesis-required` | Off | Enable explicit thesis policy; valid only for individual stocks |
| `--proxy-for TICKER` | None | Canonical US-market ticker represented by a wrapper ETF |

For example, a KRW-listed S&P 500 wrapper can be added with explicit ETF metadata:

```bash
uv run peakguard assets add 360750.KS \
  --name "TIGER 미국S&P500" \
  --currency KRW \
  --asset-type core_etf \
  --portfolio-group us_equity \
  --proxy-for SPY
```

The command rejects duplicate tickers and invalid field combinations before
changing the file. A successful add takes effect on the next scheduled run; a new
ticker without remote history is bootstrapped from one year of closing prices.

#### Update a tracked asset

Update only the fields supplied on the command line. Other fields remain unchanged.
For example, enable explicit thesis review for an existing individual stock:

```bash
uv run peakguard assets update SPCX --thesis-required
```

Disable it explicitly with the paired boolean option:

```bash
uv run peakguard assets update SPCX --no-thesis-required
```

The update command also accepts `--name`, `--threshold`, `--currency`,
`--asset-type`, `--portfolio-group`, and `--proxy-for`. At least one update option
is required, the ticker must already exist, and the complete resulting entry must
remain valid. For example:

```bash
uv run peakguard assets update SPCX --threshold 20 --name "SpaceX"
```

#### Remove a tracked asset

Interactive removal asks for confirmation:

```bash
uv run peakguard assets remove AAPL
```

For scripts or other non-interactive use, confirmation can be skipped explicitly:

```bash
uv run peakguard assets remove AAPL --yes
```

Removal stops future monitoring but does not delete historical rows already stored
in the Gist. If the ticker is added again, normal rolling-window processing resumes.

#### Prune removed ticker history

Gist history is never pruned automatically by the scheduled workflow. The manual
command defaults to a dry run and lists untracked tickers with their row counts and
date ranges:

```bash
uv run peakguard history prune
```

Preview one removed ticker, then apply only that deletion:

```bash
uv run peakguard history prune --ticker AMZN
uv run peakguard history prune --ticker AMZN --apply
```

`--ticker` can be repeated to select several removed tickers. The command refuses to
prune a ticker that still exists in `config/portfolio.yaml`.

Applying every untracked candidate asks for an additional confirmation:

```bash
uv run peakguard history prune --apply
```

For deliberate non-interactive batch cleanup, supply both mutation flags:

```bash
uv run peakguard history prune --apply --yes
```

History commands require `GIST_ID` and `GIST_PAT` in the process environment. A
local `.env` file is not loaded automatically; export it before running the command:

```bash
set -a
source .env
set +a
uv run peakguard history prune --ticker AMZN
```

The command first parses the complete remote CSV and writes through the same Gist
client used by the daily service. Without `--apply`, it never modifies remote data.

#### Storage and validation behavior

Add, update, and remove commands validate both the complete ticker configuration and
global alert thresholds before replacing `config/portfolio.yaml`. Replacement is
atomic, so an invalid command cannot leave a partially written configuration. YAML
key order is retained, but comments and cosmetic quoting may be normalized when a
mutation is saved. Review and commit the resulting configuration change through the
normal project workflow.

---

## Architecture

```
src/
└── peakguard/
    ├── main.py        # Pipeline orchestration
    ├── mdd_calc.py    # Pure domain logic (drawdown, Z-score, bounce, rolling ATH)
    ├── storage.py     # CSV serialization/deserialization & local file I/O
    ├── config.py      # YAML config loader
    ├── cli.py         # Tracked-asset list/add/update/remove command
    ├── portfolio_context.py # Optional PortfoTrack snapshot validation
    ├── portfolio_action.py  # Pure allocation-guidance classification
    ├── fetcher.py     # yfinance wrapper (price & history fetching)
    ├── notifier.py    # Telegram Bot API wrapper (all alert types)
    ├── gist_client.py # GitHub Gist API wrapper (remote CSV persistence)
    └── errors.py      # Custom error hierarchy
```

**Layered Design:**

- **Domain** (`mdd_calc`, `portfolio_action`) — Pure signal and allocation-guidance logic, no I/O or network calls
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
| `PORTFOTRACK_CONTEXT_B64` | Optional Base64-encoded PortfoTrack export for GitHub Actions |

These are injected automatically via GitHub Actions Secrets in production.

To refresh portfolio context without committing personal amounts, encode the latest
PortfoTrack export directly into the optional repository secret:

```bash
base64 < /path/to/portfotrack-allocation-YYYY-MM-DD-v1.json \
  | tr -d '\n' \
  | gh secret set PORTFOTRACK_CONTEXT_B64 --repo OWNER/PeakGuard
```

The scheduled workflow restores the secret only inside its ephemeral runner. If the
secret is absent, PeakGuard continues in price-only mode.

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
