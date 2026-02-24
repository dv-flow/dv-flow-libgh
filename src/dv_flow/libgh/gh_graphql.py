"""
gh_graphql.py — shared GraphQL helper for dv-flow-libgh.

All GitHub Discussions (and other GraphQL-only) operations use this module.
"""
import asyncio
import logging
import random
from typing import Any, Dict, Optional

import httpx
from dv_flow.libgh.gh_client import GHRequestError, DEFAULT_API_VERSION

_log = logging.getLogger(__name__)
_GQL_ENDPOINT = "https://api.github.com/graphql"


async def gql_request(
    token: str,
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    retry_limit: int = 3,
    retry_backoff_ms: int = 500,
    api_version: str = DEFAULT_API_VERSION,
) -> Dict[str, Any]:
    """
    Execute a GitHub GraphQL query or mutation with bounded retries.

    Returns the ``data`` dict from the response on success.
    Raises GHRequestError on error (including GraphQL-level errors).
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": api_version,
    }
    payload: Dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    last_exc: Optional[Exception] = None

    async with httpx.AsyncClient() as client:
        for attempt in range(retry_limit + 1):
            try:
                response = await client.post(
                    _GQL_ENDPOINT,
                    headers=headers,
                    json=payload,
                )
            except httpx.TransportError as exc:
                last_exc = exc
                _log.warning("GraphQL transport error on attempt %d: %s", attempt + 1, exc)
            else:
                if response.status_code == 200:
                    body = response.json()
                    if "errors" in body:
                        msgs = "; ".join(e.get("message", str(e)) for e in body["errors"])
                        raise GHRequestError(f"GraphQL error: {msgs}")
                    return body.get("data", {})

                # Rate-limited
                if response.status_code in (403, 429):
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        await asyncio.sleep(float(retry_after))
                        continue

                if response.status_code < 500 and response.status_code not in (403, 429):
                    raise GHRequestError(
                        f"GraphQL HTTP {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

                last_exc = GHRequestError(
                    f"GraphQL HTTP {response.status_code}",
                    status_code=response.status_code,
                )
                _log.warning("GraphQL HTTP %d on attempt %d", response.status_code, attempt + 1)

            if attempt < retry_limit:
                jitter_ms = random.randint(0, retry_backoff_ms)
                backoff_s = (retry_backoff_ms * (2 ** attempt) + jitter_ms) / 1000.0
                await asyncio.sleep(backoff_s)

    raise GHRequestError(
        f"GraphQL request failed after {retry_limit + 1} attempts"
    ) from last_exc
