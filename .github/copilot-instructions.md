---
applyTo: '**'
---
# Copilot Instructions — PeakGuard

This repository contains **PeakGuard**, a zero-cost, serverless Maximum Drawdown (MDD) tracking tool.
GitHub Copilot should follow the constraints, architecture, and design principles defined below
when generating or suggesting code.

---

## 1. Project Scope & Constraints

- **Serverless Automation only**
  - Runs exclusively via GitHub Actions schedule (cron)
  - No dedicated 24/7 servers or cloud instances

- **Gist-based JSON persistence**
  - Use JSON (`peak_prices.json`) stored in a GitHub Gist
  - The `gist_client` module reads/writes via the GitHub Gist API
  - Local file I/O (`storage` module) is available for testing and development
  - No external database (e.g., PostgreSQL, MySQL) or ORM

- **Domain focus**
  - Tracking All-Time High (ATH) and current MDD for specific assets.
  - Target assets: Index-tracking ETFs (S&P 500, NASDAQ) and individual tech stocks (Amazon, Microsoft, Meta, Nvidia, Google).
  - Price checks occur only once a day (Post-market). No real-time or high-frequency tracking.

---

## 2. Core Goals

Copilot-generated code should prioritize:

1. Minimizing external API calls (fetching only necessary current prices via `yfinance`).
2. Accurately calculating MDD against the stored ATH.
3. Triggering Telegram notifications strictly when user-defined thresholds are breached.

Avoid:
- Complex technical indicators (RSI, MACD, etc.)
- Database connection pools or session management
- Any form of trading execution or prediction logic

---

## 3. Architectural Principles

### Layered Design (Strict)

Keep responsibilities separated:

- **Domain (`mdd_calc`)**
  - Pure business logic (calculating drawdown percentages, evaluating thresholds).
  - No I/O, no network calls, no file system access.

- **Storage (`storage`)**
  - JSON serialization/deserialization (`serialize_peaks`, `deserialize_peaks`).
  - Local file I/O for testing and development (`load_peaks`, `save_peaks`).
  - Contains `PeakRecord` dataclass for ATH data.

- **External Services (`fetcher`, `notifier`, `gist_client`)**
  - `fetcher`: Wraps `yfinance` to get the latest close price.
  - `notifier`: Wraps Telegram Bot API for alerts.
  - `gist_client`: Wraps GitHub Gist API for remote JSON persistence.
  - Must handle network timeouts and rate limits gracefully.

Copilot **must not** mix these layers.

---

## 4. Error Handling Policy

### External/Network errors vs Programmer errors

- **Network/API Errors**
  - Use custom error hierarchy (`FetchError`, `NotificationError`, `StorageError`, `GistError`, etc.).
  - Must not crash the entire run if one ticker fails to fetch; log the error and proceed to the next.

- **Programmer / invariant violations**
  - Use native Python exceptions (`ValueError`, `TypeError`, `KeyError`).
  - Do NOT wrap these in application error classes.

Assertions:
- ❌ Not allowed in production code
- ✅ Allowed only in tests

---

## 5. Persistence Rules

- `peak_prices.json` must:
  - Be human-readable.
  - Map tickers to their respective ATH and the date it was reached.

- **Production persistence** uses GitHub Gist:
  - `gist_client.read_gist()` / `gist_client.write_gist()` for remote I/O.
  - Requires `GIST_PAT` and `GIST_ID` environment variables.

- **Local persistence** is available for testing/development:
  - `storage.load_peaks()` / `storage.save_peaks()` for file-based I/O.

Copilot should not introduce:
- SQLite or external DB drivers.
- Asynchronous file I/O (synchronous is fine for this scale).

---

## 6. Automation & Interface Rules

- Entry point: `python src/main.py`
- Configuration: `config/portfolio.yaml` dictates tickers and alert thresholds.
- Secrets: Handled entirely via `os.environ` (injected by GitHub Actions Secrets).
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram alerts
  - `GIST_PAT` — GitHub Gist API access
  - `GIST_ID` — Target Gist ID for `peak_prices.json`

---

## 7. Code Style & Documentation

- Python version: **3.12+**
- Prefer:
  - `dataclass`
  - Explicit type annotations (e.g., `def calculate_mdd(current: float, peak: float) -> float:`)
  - Functional paradigms where appropriate.

Docstrings:
- Google style
- Required for all public functions and classes
- Describe **invariants and intent**, not obvious mechanics

---

## 8. TDD & Testing Expectations (Mandatory)

This project follows **TDD**.

### 8.1 Default workflow (Red → Green → Refactor)

When implementing or changing behavior, Copilot should:

1. **Write/Update tests first (RED)**
2. **Minimal implementation (GREEN)**
3. **Refactor (REFACTOR)**

### 8.2 Test design rules

- Use `pytest`.
- Prefer small, focused unit tests.
- **Mock external calls explicitly**: `yfinance` and Telegram API calls MUST be mocked using `unittest.mock` or `pytest-mock`. Tests must never hit real networks.
- **New tests go under `tests/` and mirror the package structure** (e.g. `src/mdd_calc.py` → `tests/test_mdd_calc.py`).

### 8.3 Coverage expectations (practical)

For new or modified logic, tests must cover:
- Happy path (Price drops below threshold -> Alert).
- Edge cases (Price hits new ATH, Price drops but above threshold).

### 8.4 No untested production changes

- Copilot should not propose production code changes without providing corresponding tests.

### 8.5 Commit & Pre-commit Policy (Mandatory)

#### 8.5.1 Pre-commit Execution Requirement
Before creating a commit, the agent **must explicitly execute pre-commit hooks** and verify that all checks pass.

Required workflow:
1. Stage changes.
2. Run: `pre-commit run --all-files`
3. Confirm formatting, lint, type checks, and tests pass.
4. Only after all checks succeed may the commit be created.

#### 8.5.2 Commit Message Convention (Commitizen + Scope Required)
This project follows **Commitizen / Conventional Commits** and **requires a scope**.

Required format:
`<type>(<scope>): <short summary>`

Constraints:
* `type`: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`
* `scope`: `domain`, `storage`, `fetcher`, `notifier`, `ci`, `tests`, `config`
* Summary must be: Short, single line, imperative mood, no trailing period.

Examples:
- `feat(domain): add MDD calculation logic`
- `fix(fetcher): handle yfinance rate limit exception`
- `test(notifier): mock telegram api response`
- `chore(ci): add github actions cron workflow`

---

## 9. What Copilot Should NOT Do

- Introduce asynchronous programming (`asyncio`, `aiohttp`) unless absolutely necessary for performance. Synchronous code is preferred for simplicity here.
- Add unnecessary dependencies outside of `yfinance`, `requests` (or `pyTelegramBotAPI`), and `pytest`.

---

## 10. Guiding Philosophy

PeakGuard values:

- **Zero-cost maintenance**: GitHub Actions and local JSON keep operational costs at $0.
- **Simplicity over cleverness**: Straightforward scripts over complex architectures.
- **Explicitness over convenience**.

When in doubt, Copilot should choose the **simplest correct solution** that aligns with long-term maintainability.
