# GitHub Actions Guide

Workflows are PeakGuard's production runtime. Preserve the zero-cost scheduled, serverless model: no always-on service or external scheduler.

- Keep the daily job runnable manually with `workflow_dispatch` and scheduled after the relevant markets close.
- Use Python 3.12 or newer consistently with `pyproject.toml`.
- The production entry point is `python src/main.py`.
- Pass `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GIST_PAT`, `GIST_ID`, and optional `PORTFOTRACK_CONTEXT_B64` only through GitHub Actions secrets and environment variables. Never echo their values or decoded portfolio context.
- Materialize optional PortfoTrack context only inside the ephemeral runner with restrictive permissions. An absent secret must preserve price-only operation.
- Keep workflow permissions least-privileged. Gist access is performed with `GIST_PAT`; repository `contents` access should remain read-only unless a concrete workflow requirement says otherwise.
- Pin official actions to deliberate major versions and review behavior before upgrading.
- Keep the job synchronous and straightforward. Do not add databases, deployed services, or parallel ticker jobs that undermine the consolidated report and shared-history update.

When changing the workflow, validate the YAML via `uv run pre-commit run --all-files` and keep commands aligned with the documented local workflow and dependency configuration.
