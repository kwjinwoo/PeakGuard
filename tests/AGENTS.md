# Test Suite Guide

Use pytest and follow red → green → refactor for every behavior change. Tests mirror the application modules: changes to `src/peakguard/<module>.py` belong primarily in `tests/test_<module>.py`; end-to-end orchestration behavior belongs in `test_main.py`.

## Test design

- Keep tests focused on one observable behavior with clear arrange, act, and assert phases.
- Cover the happy path, validation and boundary cases, and the relevant failure path. For alert logic, include a breached threshold, an exact threshold boundary, a price below ATH but above the threshold, and a new or changed rolling ATH as applicable.
- Use fixed `date` values rather than the wall clock so rolling-window behavior is deterministic.
- Assert public outcomes and meaningful collaborator calls rather than private implementation details.
- Production assertions are forbidden, but normal pytest `assert` statements are expected here.

## Isolation

- Never access the network. Mock `yfinance`, `requests`, Telegram, and Gist interactions with `unittest.mock` or `pytest-mock` at the symbol location used by the module under test.
- Use `tmp_path` for local file behavior and `monkeypatch` for environment variables. Do not depend on developer-machine state, credentials, execution order, or files outside test fixtures.
- Test custom errors for expected storage/network failures and native exceptions for invalid arguments or violated invariants.
- When testing partial fetch failures, verify remaining tickers still complete and the failure is included in the consolidated report.

Run `uv run pytest` while iterating, then `uv run pre-commit run --all-files` before a commit.
