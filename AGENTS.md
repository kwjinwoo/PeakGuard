# PeakGuard Agent Guide

## Project overview

PeakGuard is a zero-cost, serverless Python 3.12+ service that runs once per weekday through GitHub Actions. It tracks each configured asset's 365-day rolling high and drawdown, evaluates alert conditions, sends one consolidated Telegram report, and persists daily closing-price history as `peak_prices.csv` in a GitHub Gist.

Keep the product deliberately small: this is daily monitoring, not real-time analytics, trading execution, or price prediction. Do not introduce a long-running server, database, ORM, technical indicators unrelated to the existing alerts, or asynchronous infrastructure without an explicit requirement.

## Repository map

- `src/peakguard/`: application package; see its local `AGENTS.md` for layer and module rules.
- `tests/`: pytest suite; see its local `AGENTS.md` for TDD and mocking rules.
- `config/`: portfolio and alert configuration; see its local `AGENTS.md` for the YAML contract.
- `docs/`: human- and LLM-readable project wiki; start at `docs/README.md` and follow its local `AGENTS.md` when maintaining documentation.
- `.agents/skills/peakguard-wiki/`: repository-local Wiki read/write skill. Use `$peakguard-wiki` whenever reading, creating, restructuring, or validating files under `docs/`.
- `.github/workflows/`: scheduled production automation; see its local `AGENTS.md` for CI and secret-handling rules.
- `src/main.py`: thin executable entry point. Keep business and integration logic in `peakguard` modules.

Instructions in a nested `AGENTS.md` augment or narrow this file for that subtree.

## Engineering conventions

- Prefer the simplest correct synchronous design and minimize external API calls.
- Use explicit type annotations and immutable `dataclass` value objects where appropriate.
- Public functions and classes require Google-style docstrings describing intent, invariants, inputs, outputs, and meaningful exceptions.
- Keep secrets in environment variables. Never hard-code credentials or commit local secret files.
- Distinguish expected I/O or network failures from programmer errors: use the existing application exception hierarchy for the former and native exceptions such as `ValueError`, `TypeError`, and `KeyError` for the latter.
- Do not use `assert` in production code; assertions are for tests.
- Preserve the layered architecture and avoid unnecessary dependencies. Current runtime integrations are `yfinance`, `requests`, and PyYAML.
- Any production behavior change must include corresponding tests, following red → green → refactor.

## Development workflow

- Install dependencies with `uv sync`.
- Run the application with `python src/main.py` (requires the documented environment variables and performs real external calls).
- Run tests with `uv run pytest`.
- Run all repository checks with `uv run pre-commit run --all-files`.
- Tests must not access real networks.

Before creating a commit, stage the intended changes, explicitly run `uv run pre-commit run --all-files`, inspect any hook edits, restage as needed, and commit only after every hook passes.

Use Conventional Commits with a required scope:

`<type>(<scope>): <imperative summary>`

- Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`.
- Scopes: `domain`, `storage`, `fetcher`, `notifier`, `ci`, `tests`, `config`.
- Keep the summary short, single-line, imperative, and without a trailing period.
