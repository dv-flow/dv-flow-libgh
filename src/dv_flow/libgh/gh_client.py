"""
gh_client.py — shared httpx helpers for dv-flow-libgh.

All GitHub API tasks use this module to:
  - Resolve authentication (GitHubAuth data item → env var fallback).
  - Resolve repo coordinates (GitHubRepoRef data item).
  - Execute HTTP requests with bounded retries and jitter.
"""
import asyncio
import logging
import os
import random
from typing import Any, Dict, List, Optional

import httpx

_log = logging.getLogger(__name__)

_GH_AUTH_TYPE = "gh.GitHubAuth"
_GH_REPO_TYPE = "gh.GitHubRepoRef"
_GH_ISSUE_TYPE = "gh.GitHubIssueRef"

DEFAULT_API_BASE = "https://api.github.com"
DEFAULT_API_VERSION = "2022-11-28"


class GHRequestError(Exception):
    """Raised when a GitHub API request fails after all retries."""
    def __init__(self, msg: str, status_code: int = 0):
        super().__init__(msg)
        self.status_code = status_code


def resolve_auth(input_items: List[Any], env: Optional[Dict[str, str]] = None) -> str:
    """Return a GitHub token from a GitHubAuth data item or the environment."""
    for item in input_items:
        if getattr(item, "type", None) == _GH_AUTH_TYPE:
            token = getattr(item, "token", "")
            if token:
                return token
    # Fallback to environment
    if env is not None:
        token = env.get("GITHUB_TOKEN", "")
    else:
        token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise GHRequestError(
            "No GitHub token found. Set GITHUB_TOKEN env var or add a gh.Auth task."
        )
    return token


def resolve_repo(input_items: List[Any]) -> Dict[str, Any]:
    """Return a dict with owner, repo, api_base, api_version, retry_limit, retry_backoff_ms."""
    for item in input_items:
        if getattr(item, "type", None) == _GH_REPO_TYPE:
            return {
                "owner": getattr(item, "owner", ""),
                "repo": getattr(item, "repo", ""),
                "api_base": getattr(item, "api_base", DEFAULT_API_BASE),
                "api_version": getattr(item, "api_version", DEFAULT_API_VERSION),
                "retry_limit": getattr(item, "retry_limit", 3),
                "retry_backoff_ms": getattr(item, "retry_backoff_ms", 500),
            }
    raise GHRequestError(
        "No gh.GitHubRepoRef data item found. Add a gh.Repo task as a dependency."
    )


def resolve_issue_ref(input_items: List[Any]) -> Optional[Dict[str, Any]]:
    """Return issue number/owner/repo from a GitHubIssueRef data item, or None."""
    for item in input_items:
        if getattr(item, "type", None) == _GH_ISSUE_TYPE:
            return {
                "number": getattr(item, "number", 0),
                "owner": getattr(item, "owner", ""),
                "repo": getattr(item, "repo", ""),
            }
    return None


def _build_headers(token: str, api_version: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": api_version,
    }


async def gh_request(
    method: str,
    url: str,
    token: str,
    api_version: str = DEFAULT_API_VERSION,
    json: Optional[Dict[str, Any]] = None,
    retry_limit: int = 3,
    retry_backoff_ms: int = 500,
) -> httpx.Response:
    """
    Execute a GitHub API request with bounded retries and exponential backoff + jitter.

    Raises GHRequestError on non-2xx after exhausting retries.
    """
    headers = _build_headers(token, api_version)
    last_exc: Optional[Exception] = None

    async with httpx.AsyncClient() as client:
        for attempt in range(retry_limit + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                )
            except httpx.TransportError as exc:
                last_exc = exc
                _log.warning("Transport error on attempt %d: %s", attempt + 1, exc)
            else:
                if response.status_code < 300:
                    return response

                # Rate-limited — honour Retry-After if present
                if response.status_code in (403, 429):
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        wait_s = float(retry_after)
                        _log.warning(
                            "Rate-limited (HTTP %d), retrying after %.1fs",
                            response.status_code, wait_s,
                        )
                        await asyncio.sleep(wait_s)
                        continue

                # Non-retryable client error
                if response.status_code < 500 and response.status_code not in (403, 429):
                    raise GHRequestError(
                        f"GitHub API error {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

                last_exc = GHRequestError(
                    f"GitHub API error {response.status_code}: {response.text}",
                    status_code=response.status_code,
                )
                _log.warning(
                    "GitHub API error %d on attempt %d, will retry",
                    response.status_code, attempt + 1,
                )

            if attempt < retry_limit:
                jitter_ms = random.randint(0, retry_backoff_ms)
                backoff_s = (retry_backoff_ms * (2 ** attempt) + jitter_ms) / 1000.0
                _log.info("Backing off %.2fs before retry %d", backoff_s, attempt + 2)
                await asyncio.sleep(backoff_s)

    raise GHRequestError(
        f"GitHub API request failed after {retry_limit + 1} attempts"
    ) from last_exc
