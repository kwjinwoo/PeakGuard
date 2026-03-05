"""Config module — loads portfolio configuration from YAML.

This module reads the portfolio configuration file that defines
which tickers to track and their MDD alert thresholds.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = ["TickerConfig", "load_portfolio"]


@dataclass(frozen=True)
class TickerConfig:
    """Immutable container for a single ticker's configuration.

    Attributes:
        ticker: The ticker symbol (e.g., "AAPL").
        name: A human-readable name for the asset.
        threshold: The MDD alert threshold percentage (0 < threshold <= 100).

    Raises:
        ValueError: If ticker is empty or threshold is out of range.
    """

    ticker: str
    name: str
    threshold: float

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        if self.threshold <= 0 or self.threshold > 100:
            raise ValueError(
                f"threshold must be in the range (0, 100], got {self.threshold}"
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

        configs.append(
            TickerConfig(
                ticker=ticker,
                name=entry["name"],
                threshold=float(entry["threshold"]),
            )
        )

    return configs
