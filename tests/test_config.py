"""Tests for the config module — loading portfolio configuration."""

from pathlib import Path

import pytest

from peakguard.config import AlertThresholds, TickerConfig, load_alert_thresholds, load_portfolio


class TestTickerConfig:
    """Tests for TickerConfig dataclass validation."""

    def test_valid_ticker_config(self) -> None:
        cfg = TickerConfig(ticker="SPY", name="S&P 500 ETF", threshold=10.0)
        assert cfg.ticker == "SPY"
        assert cfg.name == "S&P 500 ETF"
        assert cfg.threshold == 10.0

    def test_empty_ticker_raises(self) -> None:
        with pytest.raises(ValueError, match="ticker"):
            TickerConfig(ticker="", name="Test", threshold=10.0)

    def test_whitespace_ticker_raises(self) -> None:
        with pytest.raises(ValueError, match="ticker"):
            TickerConfig(ticker="   ", name="Test", threshold=10.0)

    def test_threshold_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            TickerConfig(ticker="SPY", name="Test", threshold=0.0)

    def test_threshold_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            TickerConfig(ticker="SPY", name="Test", threshold=-5.0)

    def test_threshold_over_100_raises(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            TickerConfig(ticker="SPY", name="Test", threshold=100.1)

    def test_threshold_exactly_100_valid(self) -> None:
        cfg = TickerConfig(ticker="SPY", name="Test", threshold=100.0)
        assert cfg.threshold == 100.0


class TestLoadPortfolio:
    """Tests for load_portfolio YAML parsing."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        yaml_content = (
            "tickers:\n"
            "  SPY:\n"
            '    name: "S&P 500 ETF"\n'
            "    threshold: 10.0\n"
            "  AAPL:\n"
            '    name: "Apple"\n'
            "    threshold: 15.0\n"
        )
        config_file = tmp_path / "portfolio.yaml"
        config_file.write_text(yaml_content)

        result = load_portfolio(config_file)

        assert len(result) == 2
        assert result[0].ticker == "SPY"
        assert result[0].name == "S&P 500 ETF"
        assert result[0].threshold == 10.0
        assert result[1].ticker == "AAPL"
        assert result[1].name == "Apple"
        assert result[1].threshold == 15.0

    def test_load_file_not_found_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            load_portfolio(missing)

    def test_load_missing_tickers_key_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("other_key: value\n")

        with pytest.raises(ValueError, match="tickers"):
            load_portfolio(config_file)

    def test_load_missing_threshold_raises(self, tmp_path: Path) -> None:
        yaml_content = "tickers:\n" "  SPY:\n" '    name: "S&P 500 ETF"\n'
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="threshold"):
            load_portfolio(config_file)

    def test_load_missing_name_raises(self, tmp_path: Path) -> None:
        yaml_content = "tickers:\n" "  SPY:\n" "    threshold: 10.0\n"
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="name"):
            load_portfolio(config_file)

    def test_load_default_portfolio_yaml(self) -> None:
        """Integration: load the actual config/portfolio.yaml."""
        project_root = Path(__file__).resolve().parent.parent
        config_path = project_root / "config" / "portfolio.yaml"

        result = load_portfolio(config_path)

        tickers = [cfg.ticker for cfg in result]
        assert "AMZN" in tickers
        assert "NVDA" in tickers
        assert len(result) >= 5


# ---------------------------------------------------------------------------
# AlertThresholds dataclass
# ---------------------------------------------------------------------------


class TestAlertThresholds:
    """Tests for the AlertThresholds dataclass validation."""

    def test_valid_thresholds(self) -> None:
        t = AlertThresholds(
            days_since_ath_limit=180,
            zscore_threshold=-2.0,
            bounce_from_bottom_min=3.0,
        )
        assert t.days_since_ath_limit == 180
        assert t.zscore_threshold == -2.0
        assert t.bounce_from_bottom_min == 3.0

    def test_rejects_non_positive_days_limit(self) -> None:
        with pytest.raises(ValueError, match="days_since_ath_limit"):
            AlertThresholds(
                days_since_ath_limit=0,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=3.0,
            )

    def test_rejects_positive_zscore_threshold(self) -> None:
        with pytest.raises(ValueError, match="zscore_threshold"):
            AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=1.0,
                bounce_from_bottom_min=3.0,
            )

    def test_rejects_negative_bounce_min(self) -> None:
        with pytest.raises(ValueError, match="bounce_from_bottom_min"):
            AlertThresholds(
                days_since_ath_limit=180,
                zscore_threshold=-2.0,
                bounce_from_bottom_min=-1.0,
            )


# ---------------------------------------------------------------------------
# load_alert_thresholds
# ---------------------------------------------------------------------------


class TestLoadAlertThresholds:
    """Tests for loading alert thresholds from YAML."""

    def test_load_valid_thresholds(self, tmp_path: Path) -> None:
        yaml_content = (
            "tickers:\n"
            "  SPY:\n"
            '    name: "S&P 500"\n'
            "    threshold: 10.0\n"
            "alert_thresholds:\n"
            "  days_since_ath_limit: 180\n"
            "  zscore_threshold: -2.0\n"
            "  bounce_from_bottom_min: 3.0\n"
        )
        config_file = tmp_path / "portfolio.yaml"
        config_file.write_text(yaml_content)

        result = load_alert_thresholds(config_file)

        assert result.days_since_ath_limit == 180
        assert result.zscore_threshold == -2.0
        assert result.bounce_from_bottom_min == 3.0

    def test_raises_when_section_missing(self, tmp_path: Path) -> None:
        yaml_content = "tickers:\n  SPY:\n    name: Test\n    threshold: 10.0\n"
        config_file = tmp_path / "portfolio.yaml"
        config_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="alert_thresholds"):
            load_alert_thresholds(config_file)

    def test_raises_when_key_missing(self, tmp_path: Path) -> None:
        yaml_content = (
            "tickers:\n"
            "  SPY:\n"
            '    name: "S&P 500"\n'
            "    threshold: 10.0\n"
            "alert_thresholds:\n"
            "  days_since_ath_limit: 180\n"
            "  zscore_threshold: -2.0\n"
        )
        config_file = tmp_path / "portfolio.yaml"
        config_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="bounce_from_bottom_min"):
            load_alert_thresholds(config_file)

    def test_raises_when_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError):
            load_alert_thresholds(missing)

    def test_load_default_portfolio_yaml(self) -> None:
        """Integration: load the actual config/portfolio.yaml."""
        project_root = Path(__file__).resolve().parent.parent
        config_path = project_root / "config" / "portfolio.yaml"

        result = load_alert_thresholds(config_path)

        assert result.days_since_ath_limit > 0
        assert result.zscore_threshold < 0
        assert result.bounce_from_bottom_min >= 0
