"""Gist client module — reads and writes JSON data via the GitHub Gist API.

This module is part of the External Services layer. It handles all
interaction with the GitHub Gist API for persisting peak price data
without committing files directly to the repository.
"""

import logging
import os

import requests

from peakguard.errors import GistError

__all__ = ["read_gist", "write_gist"]

logger = logging.getLogger(__name__)

_GIST_API_URL = "https://api.github.com/gists/{gist_id}"
_REQUEST_TIMEOUT_SECONDS = 10


def _get_github_token() -> str:
    """Read and validate GITHUB_TOKEN from environment variables.

    Returns:
        The GitHub personal access token.

    Raises:
        ValueError: If GITHUB_TOKEN is missing or empty.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    return token


def _build_headers(token: str) -> dict[str, str]:
    """Build HTTP headers for GitHub API requests.

    Args:
        token: The GitHub personal access token.

    Returns:
        A dict of HTTP headers including authorization and accept.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def read_gist(*, gist_id: str, filename: str) -> str:
    """Read a file's content from a GitHub Gist.

    Args:
        gist_id: The ID of the Gist to read from.
        filename: The name of the file within the Gist.

    Returns:
        The raw text content of the file.

    Raises:
        ValueError: If GITHUB_TOKEN is missing (programmer error).
        GistError: If the API call fails or the file is not found.
    """
    token = _get_github_token()
    url = _GIST_API_URL.format(gist_id=gist_id)

    try:
        response = requests.get(
            url,
            headers=_build_headers(token),
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise GistError(message=str(exc)) from exc

    files = response.json().get("files", {})
    if filename not in files:
        raise GistError(
            message=f"File '{filename}' not found in gist '{gist_id}'"
        )

    return files[filename]["content"]


def write_gist(*, gist_id: str, filename: str, content: str) -> None:
    """Write (update) a file's content in a GitHub Gist.

    Args:
        gist_id: The ID of the Gist to update.
        filename: The name of the file within the Gist.
        content: The new text content for the file.

    Raises:
        ValueError: If GITHUB_TOKEN is missing (programmer error).
        GistError: If the API call fails.
    """
    token = _get_github_token()
    url = _GIST_API_URL.format(gist_id=gist_id)

    try:
        response = requests.patch(
            url,
            headers=_build_headers(token),
            json={"files": {filename: {"content": content}}},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise GistError(message=str(exc)) from exc
