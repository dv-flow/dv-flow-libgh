"""
issues.py — pytask implementations for gh.issues.{Create,Update,Close}.
"""
import logging
from typing import Any, List

from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError,
    resolve_auth,
    resolve_repo,
    resolve_issue_ref,
    gh_request,
)

_log = logging.getLogger(__name__)


async def IssuesCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a new GitHub issue; outputs a gh.GitHubIssueRef data item."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    title = getattr(input.params, "title", "") or ""
    if not title:
        ctxt.error("gh.issues.Create: 'title' parameter is required.")
        return TaskDataResult(status=1)

    body: dict = {"title": title}
    body_text = getattr(input.params, "body", "") or ""
    if body_text:
        body["body"] = body_text
    labels = getattr(input.params, "labels", None) or []
    if labels:
        body["labels"] = list(labels)
    assignees = getattr(input.params, "assignees", None) or []
    if assignees:
        body["assignees"] = list(assignees)
    milestone = getattr(input.params, "milestone", 0) or 0
    if milestone:
        body["milestone"] = milestone

    url = (
        f"{repo_info['api_base']}/repos/"
        f"{repo_info['owner']}/{repo_info['repo']}/issues"
    )

    try:
        response = await gh_request(
            "POST", url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.issues.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubIssueRef",
        number=data["number"],
        html_url=data["html_url"],
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Created issue #%d: %s", data["number"], data["html_url"])
    return TaskDataResult(status=0, output=[item])


async def IssuesUpdate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update an existing GitHub issue; outputs an updated gh.GitHubIssueRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    # Resolve issue number: param overrides data item
    number = getattr(input.params, "number", 0) or 0
    if not number:
        ref = resolve_issue_ref(input.inputs)
        if ref:
            number = ref["number"]
    if not number:
        ctxt.error("gh.issues.Update: issue number required via 'number' param or gh.GitHubIssueRef input.")
        return TaskDataResult(status=1)

    body: dict = {}
    title = getattr(input.params, "title", "") or ""
    if title:
        body["title"] = title
    body_text = getattr(input.params, "body", "") or ""
    if body_text:
        body["body"] = body_text
    labels = getattr(input.params, "labels", None)
    if labels is not None and len(labels):
        body["labels"] = list(labels)
    assignees = getattr(input.params, "assignees", None)
    if assignees is not None and len(assignees):
        body["assignees"] = list(assignees)
    state = getattr(input.params, "state", "") or ""
    if state:
        body["state"] = state

    url = (
        f"{repo_info['api_base']}/repos/"
        f"{repo_info['owner']}/{repo_info['repo']}/issues/{number}"
    )

    try:
        response = await gh_request(
            "PATCH", url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.issues.Update failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubIssueRef",
        number=data["number"],
        html_url=data["html_url"],
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Updated issue #%d", data["number"])
    return TaskDataResult(status=0, output=[item])


async def IssuesClose(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Close a GitHub issue; outputs an updated gh.GitHubIssueRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    number = getattr(input.params, "number", 0) or 0
    if not number:
        ref = resolve_issue_ref(input.inputs)
        if ref:
            number = ref["number"]
    if not number:
        ctxt.error("gh.issues.Close: issue number required via 'number' param or gh.GitHubIssueRef input.")
        return TaskDataResult(status=1)

    url = (
        f"{repo_info['api_base']}/repos/"
        f"{repo_info['owner']}/{repo_info['repo']}/issues/{number}"
    )

    try:
        response = await gh_request(
            "PATCH", url, token,
            api_version=repo_info["api_version"],
            json={"state": "closed"},
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.issues.Close failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubIssueRef",
        number=data["number"],
        html_url=data["html_url"],
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Closed issue #%d", data["number"])
    return TaskDataResult(status=0, output=[item])
