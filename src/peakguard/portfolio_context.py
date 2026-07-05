"""Load and validate the PortfoTrack allocation-context export."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "AllocationGroup",
    "AllocationStatus",
    "PortfolioContext",
    "load_portfolio_context",
]

_SUPPORTED_SCHEMA_VERSION = "1.0"
_RATIO_TOLERANCE = 1e-9


class AllocationStatus(StrEnum):
    """PortfoTrack allocation state relative to configured target bounds."""

    BELOW_TOLERANCE = "below_tolerance"
    WITHIN_TOLERANCE = "within_tolerance"
    ABOVE_TOLERANCE = "above_tolerance"


@dataclass(frozen=True)
class AllocationGroup:
    """Immutable allocation facts for one PortfoTrack asset class.

    Attributes:
        asset_id: Stable PortfoTrack asset-class identifier.
        current_amount: Current amount in the context snapshot currency.
        current_weight: Current allocation ratio from 0.0 to 1.0.
        target_weight: Target allocation ratio from 0.0 to 1.0.
        target_lower: Inclusive lower target bound.
        target_upper: Inclusive upper target bound.
        drift_percentage_points: Current minus target weight in percentage points.
        status: Current weight's position relative to the target bounds.
    """

    asset_id: str
    current_amount: int
    current_weight: float
    target_weight: float
    target_lower: float
    target_upper: float
    drift_percentage_points: float
    status: AllocationStatus

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id must be a non-empty string")
        if self.current_amount < 0:
            raise ValueError("current_amount must be non-negative")
        for field, value in (
            ("current_weight", self.current_weight),
            ("target_weight", self.target_weight),
            ("target_range.lower", self.target_lower),
            ("target_range.upper", self.target_upper),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field} must be in the range [0, 1]")
        if self.target_lower > self.target_upper:
            raise ValueError("target_range lower must not exceed upper")

        expected_status = self._derive_status()
        if self.status is not expected_status:
            raise ValueError(
                f"status {self.status.value!r} is inconsistent with current_weight "
                f"for asset_id {self.asset_id!r}"
            )
        expected_drift = (self.current_weight - self.target_weight) * 100
        if not math.isclose(
            self.drift_percentage_points,
            expected_drift,
            abs_tol=_RATIO_TOLERANCE,
        ):
            raise ValueError(
                "drift_percentage_points is inconsistent with current_weight "
                "and target_weight"
            )

    def _derive_status(self) -> AllocationStatus:
        if self.current_weight < self.target_lower:
            return AllocationStatus.BELOW_TOLERANCE
        if self.current_weight > self.target_upper:
            return AllocationStatus.ABOVE_TOLERANCE
        return AllocationStatus.WITHIN_TOLERANCE


@dataclass(frozen=True)
class PortfolioContext:
    """Immutable validated PortfoTrack allocation snapshot.

    Attributes:
        schema_version: PortfoTrack export schema version.
        as_of: Date of the explicitly selected PortfoTrack snapshot.
        currency: Currency used by all snapshot amounts.
        total_assets: Total portfolio amount in ``currency``.
        groups: Allocation facts keyed by stable PortfoTrack asset ID.
    """

    schema_version: str
    as_of: date
    currency: str
    total_assets: int
    groups: Mapping[str, AllocationGroup]

    def __post_init__(self) -> None:
        if self.schema_version != _SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {self.schema_version!r}; "
                f"expected {_SUPPORTED_SCHEMA_VERSION!r}"
            )
        if not self.currency.strip():
            raise ValueError("snapshot.currency must be a non-empty string")
        if self.total_assets < 0:
            raise ValueError("snapshot.total_amount must be non-negative")

        immutable_groups = MappingProxyType(dict(self.groups))
        object.__setattr__(self, "groups", immutable_groups)
        if (
            sum(group.current_amount for group in immutable_groups.values())
            != self.total_assets
        ):
            raise ValueError(
                "snapshot.total_amount must equal summed asset current_amount"
            )
        if immutable_groups:
            if self.total_assets > 0:
                for group in immutable_groups.values():
                    expected_weight = group.current_amount / self.total_assets
                    if not math.isclose(
                        group.current_weight,
                        expected_weight,
                        abs_tol=_RATIO_TOLERANCE,
                    ):
                        raise ValueError(
                            f"current_amount and current_weight are inconsistent "
                            f"for asset_id {group.asset_id!r}"
                        )
            current_total = sum(
                group.current_weight for group in immutable_groups.values()
            )
            expected_current_total = 1.0 if self.total_assets > 0 else 0.0
            if not math.isclose(
                current_total, expected_current_total, abs_tol=_RATIO_TOLERANCE
            ):
                raise ValueError(
                    "asset current_weight values are internally inconsistent"
                )
            target_total = sum(
                group.target_weight for group in immutable_groups.values()
            )
            if not math.isclose(target_total, 1.0, abs_tol=_RATIO_TOLERANCE):
                raise ValueError("asset target_weight values must sum to 1.0")


def load_portfolio_context(path: Path) -> PortfolioContext | None:
    """Load an optional PortfoTrack schema 1.0 allocation export.

    Args:
        path: Local path to the explicitly exported JSON context.

    Returns:
        A validated immutable context, or ``None`` when the optional file is absent.

    Raises:
        OSError: If an existing file cannot be read.
        TypeError: If a field has an invalid JSON type.
        ValueError: If JSON syntax, schema version, or invariants are invalid.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"PortfoTrack context must contain valid JSON: {exc.msg}"
        ) from exc

    root = _require_mapping(payload, "context")
    schema_version = _require_string(root, "schema_version")
    snapshot = _require_mapping(_require_field(root, "snapshot"), "snapshot")
    assets = _require_list(root, "assets")

    asset_ids = [
        _require_string(_require_mapping(item, "asset"), "asset_id") for item in assets
    ]
    if asset_ids != sorted(asset_ids):
        raise ValueError("assets must be sorted ascending by asset_id")
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("asset_id values must be unique")

    groups = {
        asset_id: _parse_group(_require_mapping(item, f"asset {asset_id!r}"))
        for asset_id, item in zip(asset_ids, assets, strict=True)
    }
    return PortfolioContext(
        schema_version=schema_version,
        as_of=_parse_date(_require_string(snapshot, "date")),
        currency=_require_string(snapshot, "currency"),
        total_assets=_require_int(snapshot, "total_amount"),
        groups=groups,
    )


def _parse_group(data: Mapping[str, object]) -> AllocationGroup:
    asset_id = _require_string(data, "asset_id")
    target_range = _require_mapping(
        _require_field(data, "target_range"), f"target_range for {asset_id!r}"
    )
    try:
        status = AllocationStatus(_require_string(data, "status"))
    except ValueError as exc:
        raise ValueError(f"invalid status for asset_id {asset_id!r}") from exc
    return AllocationGroup(
        asset_id=asset_id,
        current_amount=_require_int(data, "current_amount"),
        current_weight=_require_number(data, "current_weight"),
        target_weight=_require_number(data, "target_weight"),
        target_lower=_require_number(target_range, "lower", label="target_range.lower"),
        target_upper=_require_number(target_range, "upper", label="target_range.upper"),
        drift_percentage_points=_require_number(data, "drift_percentage_points"),
        status=status,
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("snapshot.date must be an ISO date") from exc


def _require_field(data: Mapping[str, object], field: str) -> object:
    if field not in data:
        raise ValueError(f"missing required field {field!r}")
    return data[field]


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _require_list(data: Mapping[str, object], field: str) -> list[object]:
    value = _require_field(data, field)
    if not isinstance(value, list):
        raise TypeError(f"{field} must be an array")
    return value


def _require_string(data: Mapping[str, object], field: str) -> str:
    value = _require_field(data, field)
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} must be a non-empty string")
    return value


def _require_int(data: Mapping[str, object], field: str) -> int:
    value = _require_field(data, field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    return value


def _require_number(
    data: Mapping[str, object], field: str, *, label: str | None = None
) -> float:
    value = _require_field(data, field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{label or field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label or field} must be finite")
    return number
