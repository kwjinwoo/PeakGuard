"""Tests for the gist_client module — read_gist and write_gist."""

import os
from unittest.mock import MagicMock

import pytest
import requests

from peakguard.errors import GistError
from peakguard.gist_client import read_gist, write_gist


class TestReadGist:
    """Tests for the read_gist function."""

    @pytest.fixture(autouse=True)
    def _set_env(self, mocker) -> None:
        """Provide valid GitHub env vars for every test by default."""
        mocker.patch.dict(
            os.environ,
            {"GIST_PAT": "ghp_fake_token_123"},
        )

    def test_returns_file_content_on_success(self, mocker) -> None:
        """Happy path: reads file content from a Gist."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "files": {
                "peak_prices.csv": {
                    "content": "ticker,date,price\nAAPL,2026-01-15,250.5"
                }
            }
        }
        mocker.patch("peakguard.gist_client.requests.get", return_value=mock_response)

        result = read_gist(gist_id="abc123", filename="peak_prices.csv")

        assert "AAPL" in result
        assert "250.5" in result

    def test_raises_gist_error_when_file_not_in_gist(self, mocker) -> None:
        """Requested filename not found in gist → GistError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "files": {"other_file.csv": {"content": "ticker,date,price\n"}}
        }
        mocker.patch("peakguard.gist_client.requests.get", return_value=mock_response)

        with pytest.raises(GistError, match="peak_prices.csv"):
            read_gist(gist_id="abc123", filename="peak_prices.csv")

    def test_raises_gist_error_on_http_error(self, mocker) -> None:
        """Non-2xx response from GitHub API → GistError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mocker.patch("peakguard.gist_client.requests.get", return_value=mock_response)

        with pytest.raises(GistError, match="404"):
            read_gist(gist_id="abc123", filename="peak_prices.csv")

    def test_raises_gist_error_on_network_error(self, mocker) -> None:
        """Network failure is wrapped in GistError."""
        mocker.patch(
            "peakguard.gist_client.requests.get",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(GistError, match="network down"):
            read_gist(gist_id="abc123", filename="peak_prices.csv")

    def test_raises_value_error_when_token_missing(self, mocker) -> None:
        """Missing GIST_PAT is a programmer error → ValueError."""
        mocker.patch.dict(os.environ, {}, clear=True)

        with pytest.raises(ValueError, match="GIST_PAT"):
            read_gist(gist_id="abc123", filename="peak_prices.csv")

    def test_sets_request_timeout(self, mocker) -> None:
        """requests.get is called with a timeout parameter."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "files": {"peak_prices.csv": {"content": "ticker,date,price\n"}}
        }
        mock_get = mocker.patch(
            "peakguard.gist_client.requests.get", return_value=mock_response
        )

        read_gist(gist_id="abc123", filename="peak_prices.csv")

        call_kwargs = mock_get.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] > 0

    def test_uses_correct_auth_header(self, mocker) -> None:
        """Authorization header contains the token."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "files": {"peak_prices.csv": {"content": "ticker,date,price\n"}}
        }
        mock_get = mocker.patch(
            "peakguard.gist_client.requests.get", return_value=mock_response
        )

        read_gist(gist_id="abc123", filename="peak_prices.csv")

        call_kwargs = mock_get.call_args[1]
        assert "Authorization" in call_kwargs.get("headers", {})
        assert "ghp_fake_token_123" in call_kwargs["headers"]["Authorization"]


class TestWriteGist:
    """Tests for the write_gist function."""

    @pytest.fixture(autouse=True)
    def _set_env(self, mocker) -> None:
        """Provide valid GitHub env vars for every test by default."""
        mocker.patch.dict(
            os.environ,
            {"GIST_PAT": "ghp_fake_token_123"},
        )

    def test_sends_patch_request_on_success(self, mocker) -> None:
        """Happy path: writes content to a Gist file."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch = mocker.patch(
            "peakguard.gist_client.requests.patch", return_value=mock_response
        )

        write_gist(
            gist_id="abc123",
            filename="peak_prices.csv",
            content="ticker,date,price\nAAPL,2026-01-15,250.5",
        )

        mock_patch.assert_called_once()

    def test_payload_contains_filename_and_content(self, mocker) -> None:
        """PATCH payload has correct file structure."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch = mocker.patch(
            "peakguard.gist_client.requests.patch", return_value=mock_response
        )

        write_gist(
            gist_id="abc123",
            filename="peak_prices.csv",
            content="ticker,date,price\nAAPL,2026-01-15,250.5",
        )

        call_kwargs = mock_patch.call_args[1]
        payload = call_kwargs["json"]
        assert "files" in payload
        assert "peak_prices.csv" in payload["files"]
        assert (
            payload["files"]["peak_prices.csv"]["content"]
            == "ticker,date,price\nAAPL,2026-01-15,250.5"
        )

    def test_raises_gist_error_on_http_error(self, mocker) -> None:
        """Non-2xx response from GitHub API → GistError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "422 Unprocessable"
        )
        mocker.patch("peakguard.gist_client.requests.patch", return_value=mock_response)

        with pytest.raises(GistError, match="422"):
            write_gist(
                gist_id="abc123",
                filename="peak_prices.csv",
                content="ticker,date,price\n",
            )

    def test_raises_gist_error_on_network_error(self, mocker) -> None:
        """Network failure is wrapped in GistError."""
        mocker.patch(
            "peakguard.gist_client.requests.patch",
            side_effect=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(GistError, match="network down"):
            write_gist(
                gist_id="abc123",
                filename="peak_prices.csv",
                content="ticker,date,price\n",
            )

    def test_raises_gist_error_on_timeout(self, mocker) -> None:
        """Timeout is wrapped in GistError."""
        mocker.patch(
            "peakguard.gist_client.requests.patch",
            side_effect=requests.exceptions.Timeout("read timed out"),
        )

        with pytest.raises(GistError, match="timed out"):
            write_gist(
                gist_id="abc123",
                filename="peak_prices.csv",
                content="ticker,date,price\n",
            )

    def test_raises_value_error_when_token_missing(self, mocker) -> None:
        """Missing GIST_PAT is a programmer error → ValueError."""
        mocker.patch.dict(os.environ, {}, clear=True)

        with pytest.raises(ValueError, match="GIST_PAT"):
            write_gist(
                gist_id="abc123",
                filename="peak_prices.csv",
                content="ticker,date,price\n",
            )

    def test_sets_request_timeout(self, mocker) -> None:
        """requests.patch is called with a timeout parameter."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch = mocker.patch(
            "peakguard.gist_client.requests.patch", return_value=mock_response
        )

        write_gist(
            gist_id="abc123",
            filename="peak_prices.csv",
            content="ticker,date,price\n",
        )

        call_kwargs = mock_patch.call_args[1]
        assert "timeout" in call_kwargs
        assert call_kwargs["timeout"] > 0

    def test_uses_correct_auth_header(self, mocker) -> None:
        """Authorization header contains the token."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_patch = mocker.patch(
            "peakguard.gist_client.requests.patch", return_value=mock_response
        )

        write_gist(
            gist_id="abc123",
            filename="peak_prices.csv",
            content="ticker,date,price\n",
        )

        call_kwargs = mock_patch.call_args[1]
        assert "Authorization" in call_kwargs.get("headers", {})
        assert "ghp_fake_token_123" in call_kwargs["headers"]["Authorization"]
