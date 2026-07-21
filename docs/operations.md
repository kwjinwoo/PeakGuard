---
id: operations
title: Operations
type: operations
status: active
last_verified: 2026-07-21
related:
  - architecture.md
  - runbooks/README.md
  - concepts/data-contracts.md
  - decisions/0007-manual-history-pruning.md
code:
  - .github/workflows/mdd-check.yml
  - src/peakguard/main.py
  - src/peakguard/gist_client.py
  - src/peakguard/notifier.py
  - src/peakguard/portfolio_context.py
  - src/peakguard/cli.py
---

# Operations

PeakGuard runs from `.github/workflows/mdd-check.yml` using `python src/main.py`. The workflow can also be started manually with `workflow_dispatch`.

## GitHub Actions secrets

| Variable | Required | Purpose |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Yes | Authorizes the Telegram Bot API request |
| `TELEGRAM_CHAT_ID` | Yes | Selects the report destination |
| `GIST_PAT` | Yes | Authorizes GitHub Gist reads and writes |
| `GIST_ID` | Yes | Selects the Gist containing `peak_prices.csv` |
| `PORTFOTRACK_CONTEXT_B64` | No | Carries a Base64-encoded PortfoTrack export into the ephemeral runner |

Secrets are supplied through environment variables. They must not appear in configuration, logs, fixtures, documentation examples, or committed files.

## Optional PortfoTrack input

An explicitly exported PortfoTrack allocation snapshot may be placed at
`config/portfotrack_context.json`. It is local, read-only, optional, and ignored by
Git because it contains personal portfolio amounts. An absent file preserves
price-only operation. An existing malformed, unsupported, internally inconsistent,
or future-dated export aborts before Gist, provider, or Telegram calls. Context that
is 8–30 days old is stale; context at least 31 days old disables future allocation
guidance while preserving price-only processing.

### Publish context to Actions

After exporting an explicitly selected PortfoTrack snapshot, update the repository
secret directly from the file without writing an encoded copy to disk:

```bash
base64 < /path/to/portfotrack-allocation-YYYY-MM-DD-v1.json \
  | tr -d '\n' \
  | gh secret set PORTFOTRACK_CONTEXT_B64 --repo OWNER/PeakGuard
```

GitHub Actions secrets are limited to 48 KB, and Base64 expands input size. Keep the
source export below approximately 36 KB. The export is expected to be much smaller.

The workflow exposes this secret only to the restore step, applies `umask 077`, and
decodes it to `config/portfotrack_context.json` before running PeakGuard. Neither the
encoded secret nor decoded JSON may be printed. The runner is ephemeral; no context
file is committed or uploaded as an artifact.

Refreshing the PortfoTrack snapshot does not automatically refresh the secret. Run
the command again whenever allocation context should change. The existing freshness
policy warns after 7 days and disables allocation guidance after 30 days.

## Persistence

Production history is a human-readable Gist file named `peak_prices.csv` with the header:

```csv
ticker,date,price
```

Rows are sorted by ticker and date. Local storage functions exist for development and testing, but the production pipeline reads and writes through `peakguard.gist_client`.

### Manual history pruning

Removing a ticker from configuration does not remove its existing Gist rows, and the
scheduled workflow never prunes them automatically. Preview all untracked history:

```bash
uv run peakguard history prune
```

Preview or apply one explicitly selected ticker:

```bash
uv run peakguard history prune --ticker AMZN
uv run peakguard history prune --ticker AMZN --apply
```

Applying every displayed untracked candidate requires an interactive confirmation.
Non-interactive operation must provide both flags:

```bash
uv run peakguard history prune --apply --yes
```

The command requires `GIST_ID` and `GIST_PAT`, displays row counts and date ranges,
and refuses to delete history for any currently configured ticker. Dry-run output
does not write to the Gist. See [ADR-0007](decisions/0007-manual-history-pruning.md).

## Failure behavior

- One ticker fetch failure is collected and processing continues with other tickers.
- Updated history is written before Telegram delivery so the report contains the final Gist-write outcome.
- Telegram request failures are logged after the persistence attempt and do not roll back a successful write.
- Missing required environment variables are fatal validation errors.
- Network requests use finite timeouts and typed integration errors.
- Treat malformed persisted data as an operational incident; do not silently invent replacement history without confirming intended recovery behavior.
- Bootstrap automatically only when `peak_prices.csv` is absent from an otherwise valid Gist response. All other Gist read or history-parse failures stop the run before evaluation and remote writes.
- Fatal Gist read and write failures attempt a data-health report and are then re-raised so GitHub Actions marks the run failed.

## Local commands

```bash
uv sync
uv run pytest
uv run pre-commit run --all-files
```

Running `python src/main.py` performs real provider, Telegram, and Gist operations and therefore requires deliberate credential setup. Unit tests must always mock those boundaries.
