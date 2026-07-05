"""Config module — loads portfolio configuration from YAML.

This module reads the portfolio configuration file that defines
which tickers to track and their MDD alert thresholds.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

__all__ = [
    "AlertThresholds",
    "AssetType",
    "TickerConfig",
    "load_alert_thresholds",
    "load_portfolio",
]


class AssetType(StrEnum):
    """Supported asset categories for asset-appropriate review behavior."""

    INDIVIDUAL_STOCK = "individual_stock"
    CORE_ETF = "core_etf"
    BOND_ETF = "bond_etf"
    GOLD_PROXY = "gold_proxy"


@dataclass(frozen=True)
class TickerConfig:
    """Immutable container for a single ticker's configuration.

    Attributes:
        ticker: The ticker symbol (e.g., "AAPL").
        name: A human-readable name for the asset.
        threshold: The MDD alert threshold percentage (0 < threshold <= 100).
        currency: The currency code for price display (default: "USD").
        asset_type: Optional category used for asset-appropriate review behavior.
        portfolio_group: Optional PortfoTrack allocation group name.
        thesis_required: Whether deep discounts require an explicit thesis review.
        proxy_for: Optional canonical US ticker whose exposure this ticker represents.

    Raises:
        TypeError: If optional metadata has an invalid type.
        ValueError: If a value is empty, out of range, or incompatible.
    """

    ticker: str
    name: str
    threshold: float
    currency: str = "USD"
    asset_type: AssetType | None = None
    portfolio_group: str | None = None
    thesis_required: bool = False
    proxy_for: str | None = None

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if self.threshold <= 0 or self.threshold > 100:
            raise ValueError(
                f"threshold must be in the range (0, 100], got {self.threshold}"
            )
        if self.asset_type is not None and not isinstance(self.asset_type, AssetType):
            raise TypeError("asset_type must be an AssetType or None")
        self._validate_optional_string("portfolio_group", self.portfolio_group)
        self._validate_optional_string("proxy_for", self.proxy_for)
        if not isinstance(self.thesis_required, bool):
            raise TypeError("thesis_required must be a boolean")
        if self.thesis_required and self.asset_type is not AssetType.INDIVIDUAL_STOCK:
            raise ValueError(
                "thesis_required can be true only for asset_type individual_stock"
            )
        if self.proxy_for == self.ticker:
            raise ValueError("proxy_for must not reference the ticker itself")

    @staticmethod
    def _validate_optional_string(field: str, value: str | None) -> None:
        """Validate an optional non-empty string metadata field.

        Args:
            field: Configuration field name used in error messages.
            value: Optional value to validate.

        Raises:
            TypeError: If the value is neither a string nor ``None``.
            ValueError: If the value is a blank string.
        """
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{field} must be a string or None")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{field} must not be blank")


@dataclass(frozen=True)
class AlertThresholds:
    """Global thresholds for conditional metric alerts.

    Attributes:
        days_since_ath_limit: Days since ATH beyond which to warn.
        zscore_threshold: Z-score below which the price is considered oversold.
        bounce_from_bottom_min: Minimum bounce percentage from the 1-year low
            to signal a trend reversal.

    Raises:
        ValueError: If any threshold value is out of valid range.
    """

    days_since_ath_limit: int
    zscore_threshold: float
    bounce_from_bottom_min: float

    def __post_init__(self) -> None:
        if self.days_since_ath_limit <= 0:
            raise ValueError(
                f"days_since_ath_limit must be positive, got {self.days_since_ath_limit}"
            )
        if self.zscore_threshold >= 0:
            raise ValueError(
                f"zscore_threshold must be negative, got {self.zscore_threshold}"
            )
        if self.bounce_from_bottom_min < 0:
            raise ValueError(
                f"bounce_from_bottom_min must be non-negative, got {self.bounce_from_bottom_min}"
            )


def load_portfolio(path: Path) -> list[TickerConfig]:
    """Load portfolio configuration from a YAML file.

    Reads the YAML file at the given path and constructs a list of
    TickerConfig objects from the ``tickers`` section.

    Args:
        path: The file path to the YAML configuration file.

    Returns:
        A list of TickerConfig objects, one per configured ticker.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the YAML structure is invalid or missing required fields.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict) or "tickers" not in raw:
        raise ValueError("Config YAML must contain a 'tickers' key")

    tickers_section = raw["tickers"]
    configs: list[TickerConfig] = []

    for ticker, entry in tickers_section.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid config for ticker '{ticker}'")
        if "name" not in entry:
            raise ValueError(f"Missing 'name' for ticker '{ticker}'")
        if "threshold" not in entry:
            raise ValueError(f"Missing 'threshold' for ticker '{ticker}'")

        raw_asset_type = entry.get("asset_type")
        if raw_asset_type is not None and not isinstance(raw_asset_type, str):
            raise TypeError(f"asset_type for ticker '{ticker}' must be a string")
        try:
            asset_type = (
                AssetType(raw_asset_type) if raw_asset_type is not None else None
            )
        except ValueError as exc:
            allowed = ", ".join(asset.value for asset in AssetType)
            raise ValueError(
                f"Invalid asset_type for ticker '{ticker}': {raw_asset_type!r}; "
                f"expected one of {allowed}"
            ) from exc

        configs.append(
            TickerConfig(
                ticker=ticker,
                name=entry["name"],
                threshold=float(entry["threshold"]),
                currency=entry.get("currency", "USD"),
                asset_type=asset_type,
                portfolio_group=entry.get("portfolio_group"),
                thesis_required=entry.get("thesis_required", False),
                proxy_for=entry.get("proxy_for"),
            )
        )

    return configs


def load_alert_thresholds(path: Path) -> AlertThresholds:
    """Load alert threshold configuration from a YAML file.

    Reads the ``alert_thresholds`` section of the YAML configuration
    and constructs an AlertThresholds object.

    Args:
        path: The file path to the YAML configuration file.

    Returns:
        An AlertThresholds object with the configured values.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the YAML structure is invalid or missing required fields.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict) or "alert_thresholds" not in raw:
        raise ValueError("Config YAML must contain an 'alert_thresholds' key")

    section = raw["alert_thresholds"]
    required_keys = [
        "days_since_ath_limit",
        "zscore_threshold",
        "bounce_from_bottom_min",
    ]

    for key in required_keys:
        if key not in section:
            raise ValueError(f"Missing '{key}' in alert_thresholds section")

    return AlertThresholds(
        days_since_ath_limit=int(section["days_since_ath_limit"]),
        zscore_threshold=float(section["zscore_threshold"]),
        bounce_from_bottom_min=float(section["bounce_from_bottom_min"]),
    )
