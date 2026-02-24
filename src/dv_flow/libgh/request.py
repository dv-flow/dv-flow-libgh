"""
request.py — pytask implementations for gh.request.{Rest,GraphQL} escape-hatch tasks.
"""
import json
import logging
import os
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError, resolve_auth, resolve_repo, gh_request,
    DEFAULT_API_BASE, DEFAULT_API_VERSION,
)
from dv_flow.libgh.gh_graphql import gql_request

_log = logging.getLogger(__name__)


async def RestRequest(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Execute a raw REST request; writes response.json and outputs GitHubRequestMeta."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    # Best-effort repo info for placeholder substitution
    try:
        repo_info = resolve_repo(input.inputs)
    except GHRequestError:
        repo_info = {
            "owner": "", "repo": "",
            "api_base": DEFAULT_API_BASE,
            "api_version": DEFAULT_API_VERSION,
            "retry_limit": 3,
            "retry_backoff_ms": 500,
        }

    method = getattr(input.params, "method", "GET") or "GET"
    path = getattr(input.params, "path", "") or ""
    if not path:
        ctxt.error("gh.request.Rest: 'path' parameter is required.")
        return TaskDataResult(status=1)

    # Substitute {owner}/{repo} placeholders
    path = path.replace("{owner}", repo_info["owner"]).replace("{repo}", repo_info["repo"])

    url = repo_info["api_base"].rstrip("/") + "/" + path.lstrip("/")

    body_param = getattr(input.params, "body", None)
    body = dict(body_param) if body_param else None

    try:
        response = await gh_request(
            method, url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.request.Rest failed: {exc}")
        return TaskDataResult(status=1)

    # Write raw response to rundir
    out_path = os.path.join(ctxt.rundir, "response.json")
    with open(out_path, "w") as fh:
        json.dump(response.json(), fh, indent=2)

    meta = ctxt.mkDataItem(
        "gh.GitHubRequestMeta",
        etag=response.headers.get("ETag", ""),
        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", -1)),
        rate_limit_reset=int(response.headers.get("X-RateLimit-Reset", 0)),
        response_status=response.status_code,
    )
    _log.info("REST %s %s -> %d", method, url, response.status_code)
    return TaskDataResult(status=0, output=[meta])


async def GraphQLRequest(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Execute a raw GraphQL request; writes response.json and outputs GitHubGraphQLMeta."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    query = getattr(input.params, "query", "") or ""
    if not query:
        ctxt.error("gh.request.GraphQL: 'query' parameter is required.")
        return TaskDataResult(status=1)

    variables_param = getattr(input.params, "variables", None)
    variables = dict(variables_param) if variables_param else None

    try:
        data = await gql_request(token, query, variables)
    except GHRequestError as exc:
        ctxt.error(f"gh.request.GraphQL failed: {exc}")
        return TaskDataResult(status=1)

    out_path = os.path.join(ctxt.rundir, "response.json")
    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=2)

    meta = ctxt.mkDataItem("gh.GitHubGraphQLMeta")
    _log.info("GraphQL query completed")
    return TaskDataResult(status=0, output=[meta])
