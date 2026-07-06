"""Tests for the scheduled production workflow contract."""

from pathlib import Path


def test_workflow_restores_optional_portfolio_context_before_run() -> None:
    """Actions secret is decoded privately before the PeakGuard entry point runs."""
    project_root = Path(__file__).resolve().parent.parent
    workflow = (project_root / ".github/workflows/mdd-check.yml").read_text(
        encoding="utf-8"
    )

    secret = "secrets.PORTFOTRACK_CONTEXT_B64"
    restore_step = "Restore PortfoTrack context"
    destination = "config/portfotrack_context.json"
    run_step = "python src/main.py"

    assert secret in workflow
    assert restore_step in workflow
    assert 'if [ -n "$PORTFOTRACK_CONTEXT_B64" ]' in workflow
    assert "base64 --decode" in workflow
    assert destination in workflow
    assert workflow.index(restore_step) < workflow.index(run_step)
    assert f"cat {destination}" not in workflow
    assert "echo $PORTFOTRACK_CONTEXT_B64" not in workflow
