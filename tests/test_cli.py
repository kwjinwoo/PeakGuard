"""Tests for the tracked-asset management CLI."""

from pathlib import Path

import pytest
import yaml

from peakguard.cli import main
from peakguard.config import AssetType, load_portfolio


def _write_config(path: Path) -> None:
    """Write a minimal valid portfolio configuration for CLI tests."""
    path.write_text(
        """tickers:
  AMZN:
    name: Amazon
    threshold: 15.0
    asset_type: individual_stock
    portfolio_group: us_equity
    thesis_required: true
alert_thresholds:
  days_since_ath_limit: 180
  zscore_threshold: -2.0
  bounce_from_bottom_min: 3.0
""",
        encoding="utf-8",
    )


def test_list_prints_tracked_assets(tmp_path: Path, capsys) -> None:
    """List shows the configured ticker and key policy fields."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)

    exit_code = main(["--config", str(config_path), "assets", "list"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AMZN" in output
    assert "Amazon" in output
    assert "individual_stock" in output
    assert "1 tracked asset" in output


def test_add_writes_valid_ticker_without_changing_thresholds(tmp_path: Path) -> None:
    """Add persists a validated asset and preserves global alert thresholds."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "assets",
            "add",
            "AAPL",
            "--name",
            "Apple",
            "--threshold",
            "12.5",
            "--asset-type",
            "individual_stock",
            "--portfolio-group",
            "us_equity",
            "--thesis-required",
        ]
    )

    configs = {config.ticker: config for config in load_portfolio(config_path)}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert configs["AAPL"].name == "Apple"
    assert configs["AAPL"].threshold == 12.5
    assert configs["AAPL"].asset_type is AssetType.INDIVIDUAL_STOCK
    assert configs["AAPL"].thesis_required is True
    assert raw["alert_thresholds"]["zscore_threshold"] == -2.0


def test_add_rejects_duplicate_without_modifying_file(tmp_path: Path, capsys) -> None:
    """Adding an existing ticker fails and leaves the configuration unchanged."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    before = config_path.read_text(encoding="utf-8")

    exit_code = main(
        [
            "--config",
            str(config_path),
            "assets",
            "add",
            "AMZN",
            "--name",
            "Amazon duplicate",
        ]
    )

    assert exit_code == 2
    assert "already tracked" in capsys.readouterr().err
    assert config_path.read_text(encoding="utf-8") == before


def test_remove_requires_confirmation_and_can_cancel(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Interactive removal leaves the ticker intact when confirmation is declined."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.setattr("builtins.input", lambda _: "n")

    exit_code = main(["--config", str(config_path), "assets", "remove", "AMZN"])

    assert exit_code == 0
    assert "Cancelled" in capsys.readouterr().out
    assert load_portfolio(config_path)[0].ticker == "AMZN"


def test_remove_yes_deletes_only_requested_ticker(tmp_path: Path) -> None:
    """The explicit yes flag removes the ticker and preserves other sections."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)

    exit_code = main(
        ["--config", str(config_path), "assets", "remove", "AMZN", "--yes"]
    )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert raw["tickers"] == {}
    assert raw["alert_thresholds"]["days_since_ath_limit"] == 180


def test_remove_unknown_ticker_does_not_modify_file(tmp_path: Path, capsys) -> None:
    """Removing an unknown ticker fails without rewriting configuration."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    before = config_path.read_text(encoding="utf-8")

    exit_code = main(
        ["--config", str(config_path), "assets", "remove", "AAPL", "--yes"]
    )

    assert exit_code == 2
    assert "not tracked" in capsys.readouterr().err
    assert config_path.read_text(encoding="utf-8") == before


def test_update_toggles_thesis_policy_and_preserves_other_fields(
    tmp_path: Path,
) -> None:
    """Update changes selected fields without replacing the ticker entry."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "assets",
            "update",
            "AMZN",
            "--no-thesis-required",
        ]
    )

    disabled = load_portfolio(config_path)[0]
    assert exit_code == 0
    assert disabled.thesis_required is False

    exit_code = main(
        [
            "--config",
            str(config_path),
            "assets",
            "update",
            "AMZN",
            "--thesis-required",
        ]
    )

    enabled = load_portfolio(config_path)[0]
    assert exit_code == 0
    assert enabled.name == "Amazon"
    assert enabled.threshold == 15.0
    assert enabled.asset_type is AssetType.INDIVIDUAL_STOCK
    assert enabled.portfolio_group == "us_equity"
    assert enabled.thesis_required is True


def test_update_unknown_ticker_does_not_modify_file(tmp_path: Path, capsys) -> None:
    """Updating an unknown ticker fails without rewriting configuration."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    before = config_path.read_text(encoding="utf-8")

    exit_code = main(
        [
            "--config",
            str(config_path),
            "assets",
            "update",
            "AAPL",
            "--thesis-required",
        ]
    )

    assert exit_code == 2
    assert "not tracked" in capsys.readouterr().err
    assert config_path.read_text(encoding="utf-8") == before


def test_update_requires_at_least_one_change(tmp_path: Path, capsys) -> None:
    """Update without any field option fails without touching the file."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    before = config_path.read_text(encoding="utf-8")

    exit_code = main(["--config", str(config_path), "assets", "update", "AMZN"])

    assert exit_code == 2
    assert "at least one" in capsys.readouterr().err
    assert config_path.read_text(encoding="utf-8") == before


_REMOTE_HISTORY = (
    "ticker,date,price\n"
    "AMZN,2026-07-18,220.0\n"
    "OLD,2026-07-17,100.0\n"
    "OLD,2026-07-18,101.0\n"
)


def test_history_prune_preview_lists_only_untracked_history(
    tmp_path: Path, mocker, monkeypatch, capsys
) -> None:
    """Default prune is a read-only preview of history absent from config."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.setenv("GIST_ID", "gist-123")
    mock_read = mocker.patch("peakguard.cli.read_gist", return_value=_REMOTE_HISTORY)
    mock_write = mocker.patch("peakguard.cli.write_gist")

    exit_code = main(["--config", str(config_path), "history", "prune"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "OLD" in output
    assert "2 rows" in output
    assert "2026-07-17" in output
    assert "2026-07-18" in output
    assert "AMZN" not in output
    assert "Dry run" in output
    mock_read.assert_called_once_with(gist_id="gist-123", filename="peak_prices.csv")
    mock_write.assert_not_called()


def test_history_prune_rejects_currently_tracked_ticker(
    tmp_path: Path, mocker, monkeypatch, capsys
) -> None:
    """A ticker still present in configuration can never be pruned."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.setenv("GIST_ID", "gist-123")
    mocker.patch("peakguard.cli.read_gist", return_value=_REMOTE_HISTORY)
    mock_write = mocker.patch("peakguard.cli.write_gist")

    exit_code = main(
        [
            "--config",
            str(config_path),
            "history",
            "prune",
            "--ticker",
            "AMZN",
            "--apply",
        ]
    )

    assert exit_code == 2
    assert "currently tracked" in capsys.readouterr().err
    mock_write.assert_not_called()


def test_history_prune_apply_removes_only_requested_ticker(
    tmp_path: Path, mocker, monkeypatch
) -> None:
    """Explicit ticker and apply update the Gist while retaining active history."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.setenv("GIST_ID", "gist-123")
    mocker.patch("peakguard.cli.read_gist", return_value=_REMOTE_HISTORY)
    mock_write = mocker.patch("peakguard.cli.write_gist")

    exit_code = main(
        [
            "--config",
            str(config_path),
            "history",
            "prune",
            "--ticker",
            "OLD",
            "--apply",
        ]
    )

    assert exit_code == 0
    content = mock_write.call_args.kwargs["content"]
    assert "AMZN,2026-07-18,220.0" in content
    assert "OLD" not in content


def test_history_prune_batch_apply_can_be_cancelled(
    tmp_path: Path, mocker, monkeypatch, capsys
) -> None:
    """Applying all untracked candidates requires another confirmation."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.setenv("GIST_ID", "gist-123")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    mocker.patch("peakguard.cli.read_gist", return_value=_REMOTE_HISTORY)
    mock_write = mocker.patch("peakguard.cli.write_gist")

    exit_code = main(["--config", str(config_path), "history", "prune", "--apply"])

    assert exit_code == 0
    assert "Cancelled" in capsys.readouterr().out
    mock_write.assert_not_called()


def test_history_prune_batch_apply_yes_skips_prompt_and_writes(
    tmp_path: Path, mocker, monkeypatch
) -> None:
    """Both mutation flags authorize non-interactive batch cleanup."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.setenv("GIST_ID", "gist-123")
    monkeypatch.setattr(
        "builtins.input", lambda _: pytest.fail("confirmation prompt was called")
    )
    mocker.patch("peakguard.cli.read_gist", return_value=_REMOTE_HISTORY)
    mock_write = mocker.patch("peakguard.cli.write_gist")

    exit_code = main(
        [
            "--config",
            str(config_path),
            "history",
            "prune",
            "--apply",
            "--yes",
        ]
    )

    assert exit_code == 0
    content = mock_write.call_args.kwargs["content"]
    assert "AMZN,2026-07-18,220.0" in content
    assert "OLD" not in content


def test_history_prune_requires_gist_id(
    tmp_path: Path, mocker, monkeypatch, capsys
) -> None:
    """A missing Gist identifier fails before any remote request."""
    config_path = tmp_path / "portfolio.yaml"
    _write_config(config_path)
    monkeypatch.delenv("GIST_ID", raising=False)
    mock_read = mocker.patch("peakguard.cli.read_gist")

    exit_code = main(["--config", str(config_path), "history", "prune"])

    assert exit_code == 2
    assert "GIST_ID" in capsys.readouterr().err
    mock_read.assert_not_called()
