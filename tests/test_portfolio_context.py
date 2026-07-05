"""Tests for loading the PortfoTrack allocation-context export."""

import json
from datetime import timedelta
from pathlib import Path

import pytest

from peakguard.portfolio_context import (
    AllocationStatus,
    ContextFreshness,
    load_portfolio_context,
)


def _valid_payload() -> dict[str, object]:
    """Return a valid two-group PortfoTrack schema 1.0 payload."""
    return {
        "schema_version": "1.0",
        "snapshot": {
            "date": "2026-07-05",
            "currency": "KRW",
            "total_amount": 10_000_000,
        },
        "assets": [
            {
                "asset_id": "bond_etf",
                "current_amount": 4_000_000,
                "current_weight": 0.4,
                "target_weight": 0.3,
                "target_range": {"lower": 0.25, "upper": 0.35},
                "drift_percentage_points": 10.0,
                "status": "above_tolerance",
            },
            {
                "asset_id": "us_equity",
                "current_amount": 6_000_000,
                "current_weight": 0.6,
                "target_weight": 0.7,
                "target_range": {"lower": 0.65, "upper": 0.75},
                "drift_percentage_points": -10.0,
                "status": "below_tolerance",
            },
        ],
    }


def _write_payload(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "portfotrack_context.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_valid_portfotrack_export(tmp_path: Path) -> None:
    context = load_portfolio_context(_write_payload(tmp_path, _valid_payload()))

    assert context is not None
    assert context.schema_version == "1.0"
    assert context.as_of.isoformat() == "2026-07-05"
    assert context.currency == "KRW"
    assert context.total_assets == 10_000_000
    assert context.groups["us_equity"].status is AllocationStatus.BELOW_TOLERANCE
    assert context.groups["us_equity"].target_lower == 0.65


def test_missing_optional_file_returns_none(tmp_path: Path) -> None:
    assert load_portfolio_context(tmp_path / "missing.json") is None


def test_accepts_empty_snapshot_with_zero_current_weights(tmp_path: Path) -> None:
    payload = _valid_payload()
    snapshot = payload["snapshot"]
    assets = payload["assets"]
    assert isinstance(snapshot, dict)
    assert isinstance(assets, list)
    snapshot["total_amount"] = 0
    for asset in assets:
        assert isinstance(asset, dict)
        asset["current_amount"] = 0
        asset["current_weight"] = 0.0
        asset["drift_percentage_points"] = -asset["target_weight"] * 100
        asset["status"] = "below_tolerance"

    context = load_portfolio_context(_write_payload(tmp_path, payload))

    assert context is not None
    assert context.total_assets == 0
    assert all(group.current_weight == 0.0 for group in context.groups.values())


def test_loaded_group_mapping_is_immutable(tmp_path: Path) -> None:
    context = load_portfolio_context(_write_payload(tmp_path, _valid_payload()))

    assert context is not None
    with pytest.raises(TypeError):
        context.groups["new"] = context.groups["us_equity"]  # type: ignore[index]


@pytest.mark.parametrize(
    ("age_days", "expected"),
    [
        (0, ContextFreshness.CURRENT),
        (7, ContextFreshness.CURRENT),
        (8, ContextFreshness.STALE),
        (30, ContextFreshness.STALE),
        (31, ContextFreshness.EXPIRED),
    ],
)
def test_classifies_context_freshness(
    tmp_path: Path, age_days: int, expected: ContextFreshness
) -> None:
    context = load_portfolio_context(_write_payload(tmp_path, _valid_payload()))
    assert context is not None

    result = context.freshness(context.as_of + timedelta(days=age_days))

    assert result is expected


def test_rejects_context_date_in_future(tmp_path: Path) -> None:
    context = load_portfolio_context(_write_payload(tmp_path, _valid_payload()))
    assert context is not None

    with pytest.raises(ValueError, match="future"):
        context.freshness(context.as_of - timedelta(days=1))


def test_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "portfotrack_context.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="valid JSON"):
        load_portfolio_context(path)


def test_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["schema_version"] = "2.0"

    with pytest.raises(ValueError, match="schema_version"):
        load_portfolio_context(_write_payload(tmp_path, payload))


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("snapshot", "date"),
        ("snapshot", "currency"),
        ("snapshot", "total_amount"),
        ("asset", "current_weight"),
        ("asset", "target_range"),
        ("asset", "status"),
    ],
)
def test_rejects_missing_required_field(
    tmp_path: Path, section: str, field: str
) -> None:
    payload = _valid_payload()
    if section == "snapshot":
        snapshot = payload["snapshot"]
        assert isinstance(snapshot, dict)
        del snapshot[field]
    else:
        assets = payload["assets"]
        assert isinstance(assets, list)
        first = assets[0]
        assert isinstance(first, dict)
        del first[field]

    with pytest.raises(ValueError, match=field):
        load_portfolio_context(_write_payload(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_weight", 1.1),
        ("target_weight", -0.1),
        ("current_amount", -1),
        ("drift_percentage_points", "ten"),
    ],
)
def test_rejects_invalid_asset_values(
    tmp_path: Path, field: str, value: object
) -> None:
    payload = _valid_payload()
    assets = payload["assets"]
    assert isinstance(assets, list)
    first = assets[0]
    assert isinstance(first, dict)
    first[field] = value

    with pytest.raises((TypeError, ValueError), match=field):
        load_portfolio_context(_write_payload(tmp_path, payload))


def test_rejects_status_inconsistent_with_weight(tmp_path: Path) -> None:
    payload = _valid_payload()
    assets = payload["assets"]
    assert isinstance(assets, list)
    first = assets[0]
    assert isinstance(first, dict)
    first["status"] = "within_tolerance"

    with pytest.raises(ValueError, match="status"):
        load_portfolio_context(_write_payload(tmp_path, payload))


def test_rejects_total_amount_mismatch(tmp_path: Path) -> None:
    payload = _valid_payload()
    snapshot = payload["snapshot"]
    assert isinstance(snapshot, dict)
    snapshot["total_amount"] = 11_000_000

    with pytest.raises(ValueError, match="total_amount"):
        load_portfolio_context(_write_payload(tmp_path, payload))


def test_rejects_group_amount_and_weight_mismatch(tmp_path: Path) -> None:
    payload = _valid_payload()
    assets = payload["assets"]
    assert isinstance(assets, list)
    first = assets[0]
    second = assets[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    first["current_weight"] = 0.6
    first["drift_percentage_points"] = 30.0
    second["current_weight"] = 0.4
    second["drift_percentage_points"] = -30.0

    with pytest.raises(ValueError, match="current_amount"):
        load_portfolio_context(_write_payload(tmp_path, payload))


def test_rejects_unsorted_asset_ids(tmp_path: Path) -> None:
    payload = _valid_payload()
    assets = payload["assets"]
    assert isinstance(assets, list)
    assets.reverse()

    with pytest.raises(ValueError, match="sorted"):
        load_portfolio_context(_write_payload(tmp_path, payload))
