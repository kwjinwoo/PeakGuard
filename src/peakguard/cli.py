"""Command-line interface for listing and mutating PeakGuard tracked assets."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
from typing import Sequence

import yaml

from peakguard.config import (
    AssetType,
    TickerConfig,
    load_alert_thresholds,
    load_portfolio,
)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "portfolio.yaml"


def _build_parser() -> argparse.ArgumentParser:
    """Build the PeakGuard command parser."""
    parser = argparse.ArgumentParser(
        prog="peakguard",
        description="Manage PeakGuard tracked assets.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_DEFAULT_CONFIG_PATH,
        help=argparse.SUPPRESS,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    assets = commands.add_parser(
        "assets", help="List, add, update, or remove tracked assets."
    )
    asset_commands = assets.add_subparsers(dest="asset_command", required=True)

    asset_commands.add_parser("list", help="List all tracked assets.")

    add = asset_commands.add_parser("add", help="Add one tracked asset.")
    add.add_argument("ticker", help="yfinance ticker symbol, such as AAPL.")
    add.add_argument("--name", required=True, help="Human-readable asset name.")
    add.add_argument(
        "--threshold",
        type=float,
        default=15.0,
        help="MDD alert threshold percentage (default: 15.0).",
    )
    add.add_argument(
        "--currency",
        default="USD",
        help="Price display currency (default: USD).",
    )
    add.add_argument(
        "--asset-type",
        choices=[asset.value for asset in AssetType],
        default=AssetType.INDIVIDUAL_STOCK.value,
        help="Asset category (default: individual_stock).",
    )
    add.add_argument(
        "--portfolio-group",
        default="us_equity",
        help="PortfoTrack asset_id (default: us_equity).",
    )
    add.add_argument(
        "--thesis-required",
        action="store_true",
        help="Require thesis review for a deep-discount individual stock.",
    )
    add.add_argument(
        "--proxy-for",
        help="Canonical US-market ticker represented by this asset.",
    )

    update = asset_commands.add_parser("update", help="Update one tracked asset.")
    update.add_argument("ticker", help="Tracked ticker symbol to update.")
    update.add_argument("--name", help="New human-readable asset name.")
    update.add_argument("--threshold", type=float, help="New MDD threshold percent.")
    update.add_argument("--currency", help="New price display currency.")
    update.add_argument(
        "--asset-type",
        choices=[asset.value for asset in AssetType],
        help="New asset category.",
    )
    update.add_argument("--portfolio-group", help="New PortfoTrack asset_id.")
    update.add_argument(
        "--thesis-required",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable explicit thesis review policy.",
    )
    update.add_argument(
        "--proxy-for",
        help="New canonical US-market ticker represented by this asset.",
    )

    remove = asset_commands.add_parser("remove", help="Remove one tracked asset.")
    remove.add_argument("ticker", help="Tracked ticker symbol to remove.")
    remove.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    return parser


def _load_raw_config(path: Path) -> dict[str, object]:
    """Load mutable YAML configuration after validating its top-level shape.

    Args:
        path: Portfolio configuration path.

    Returns:
        Mutable configuration mapping.

    Raises:
        FileNotFoundError: If the configuration does not exist.
        ValueError: If the YAML root or ticker section is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config YAML root must be a mapping")
    if not isinstance(raw.get("tickers"), dict):
        raise ValueError("Config YAML must contain a 'tickers' mapping")
    return raw


def _write_validated_config(path: Path, raw: dict[str, object]) -> None:
    """Validate and atomically replace a portfolio configuration.

    Args:
        path: Destination configuration path.
        raw: Complete configuration payload.

    Raises:
        OSError: If the temporary file or atomic replacement fails.
        TypeError: If the generated configuration has invalid field types.
        ValueError: If the generated configuration violates the schema.
    """
    serialized = yaml.safe_dump(
        raw,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        load_portfolio(temporary_path)
        load_alert_thresholds(temporary_path)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _list_assets(path: Path) -> int:
    """Print tracked assets in a compact table."""
    configs = load_portfolio(path)
    print(f"{'TICKER':<14} {'NAME':<28} {'TYPE':<18} {'MDD':>7}  GROUP")
    print(f"{'-' * 14} {'-' * 28} {'-' * 18} {'-' * 7}  {'-' * 12}")
    for config in configs:
        asset_type = config.asset_type.value if config.asset_type else "price_only"
        group = config.portfolio_group or "-"
        print(
            f"{config.ticker:<14} {config.name:<28} {asset_type:<18} "
            f"{config.threshold:>6.1f}%  {group}"
        )
    suffix = "asset" if len(configs) == 1 else "assets"
    print(f"\n{len(configs)} tracked {suffix}")
    return 0


def _add_asset(path: Path, args: argparse.Namespace) -> int:
    """Add one validated asset to the configuration."""
    raw = _load_raw_config(path)
    tickers = raw["tickers"]
    if not isinstance(tickers, dict):
        raise ValueError("Config YAML must contain a 'tickers' mapping")
    ticker = args.ticker.strip().upper()
    name = args.name.strip()
    if not name:
        raise ValueError("name must be a non-empty string")
    if ticker in tickers:
        raise ValueError(f"{ticker} is already tracked")

    config = TickerConfig(
        ticker=ticker,
        name=name,
        threshold=args.threshold,
        currency=args.currency.strip().upper(),
        asset_type=AssetType(args.asset_type),
        portfolio_group=args.portfolio_group.strip(),
        thesis_required=args.thesis_required,
        proxy_for=args.proxy_for.strip().upper() if args.proxy_for else None,
    )
    entry: dict[str, object] = {
        "name": config.name,
        "threshold": config.threshold,
        "currency": config.currency,
        "asset_type": config.asset_type.value if config.asset_type else None,
        "portfolio_group": config.portfolio_group,
    }
    if config.thesis_required:
        entry["thesis_required"] = True
    if config.proxy_for is not None:
        entry["proxy_for"] = config.proxy_for
    tickers[ticker] = entry
    _write_validated_config(path, raw)
    print(f"Added {ticker} ({name})")
    return 0


def _remove_asset(path: Path, args: argparse.Namespace) -> int:
    """Remove one tracked asset after explicit confirmation."""
    raw = _load_raw_config(path)
    tickers = raw["tickers"]
    if not isinstance(tickers, dict):
        raise ValueError("Config YAML must contain a 'tickers' mapping")
    ticker = args.ticker.strip().upper()
    if ticker not in tickers:
        raise ValueError(f"{ticker} is not tracked")
    if not args.yes:
        answer = input(f"Remove {ticker} from tracked assets? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled")
            return 0
    del tickers[ticker]
    _write_validated_config(path, raw)
    print(f"Removed {ticker}")
    return 0


def _update_asset(path: Path, args: argparse.Namespace) -> int:
    """Update selected fields on one tracked asset."""
    raw = _load_raw_config(path)
    tickers = raw["tickers"]
    if not isinstance(tickers, dict):
        raise ValueError("Config YAML must contain a 'tickers' mapping")
    ticker = args.ticker.strip().upper()
    if ticker not in tickers:
        raise ValueError(f"{ticker} is not tracked")
    entry = tickers[ticker]
    if not isinstance(entry, dict):
        raise ValueError(f"Invalid config for ticker '{ticker}'")

    changes = {
        "name": args.name,
        "threshold": args.threshold,
        "currency": args.currency,
        "asset_type": args.asset_type,
        "portfolio_group": args.portfolio_group,
        "thesis_required": args.thesis_required,
        "proxy_for": args.proxy_for,
    }
    if all(value is None for value in changes.values()):
        raise ValueError("at least one update option is required")

    for field, value in changes.items():
        if value is None:
            continue
        if field == "name":
            value = value.strip()
            if not value:
                raise ValueError("name must be a non-empty string")
        elif field == "currency":
            value = value.strip().upper()
            if not value:
                raise ValueError("currency must be a non-empty string")
        elif field == "portfolio_group":
            value = value.strip()
            if not value:
                raise ValueError("portfolio_group must be a non-empty string")
        elif field == "proxy_for":
            value = value.strip().upper()
            if not value:
                raise ValueError("proxy_for must be a non-empty string")
        entry[field] = value

    _write_validated_config(path, raw)
    print(f"Updated {ticker}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PeakGuard CLI.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Process exit code: zero for success and two for configuration errors.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.asset_command == "list":
            return _list_assets(args.config)
        if args.asset_command == "add":
            return _add_asset(args.config, args)
        if args.asset_command == "update":
            return _update_asset(args.config, args)
        if args.asset_command == "remove":
            return _remove_asset(args.config, args)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
