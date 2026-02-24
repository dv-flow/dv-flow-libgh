"""
pulls.py — pytask implementations for gh.pulls.{Create,Update,Merge}.
"""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError, resolve_auth, resolve_repo, gh_request,
)

_log = logging.getLogger(__name__)
_GH_PULL_TYPE = "gh.GitHubPullRef"


def _resolve_pull_number(input_items, params):
    """Return PR number from param (takes precedence) or GitHubPullRef item."""
    number = getattr(params, "number", 0) or 0
    if number:
        return number
    for item in input_items:
        if getattr(item, "type", None) == _GH_PULL_TYPE:
            return getattr(item, "number", 0)
    return 0


async def PullsCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a pull request; outputs a gh.GitHubPullRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    title = getattr(input.params, "title", "") or ""
    head = getattr(input.params, "head", "") or ""
    base = getattr(input.params, "base", "") or ""

    if not title or not head or not base:
        ctxt.error("gh.pulls.Create: 'title', 'head', and 'base' are required.")
        return TaskDataResult(status=1)

    body: dict = {"title": title, "head": head, "base": base}
    body_text = getattr(input.params, "body", "") or ""
    if body_text:
        body["body"] = body_text
    if getattr(input.params, "draft", False):
        body["draft"] = True

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}/pulls"
    try:
        response = await gh_request(
            "POST", url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.pulls.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubPullRef",
        number=data["number"],
        html_url=data["html_url"],
        head=data["head"]["ref"],
        base=data["base"]["ref"],
        merged=False,
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Created PR #%d: %s", data["number"], data["html_url"])
    return TaskDataResult(status=0, output=[item])


async def PullsUpdate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update a pull request; outputs an updated gh.GitHubPullRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    number = _resolve_pull_number(input.inputs, input.params)
    if not number:
        ctxt.error("gh.pulls.Update: PR number required via 'number' param or GitHubPullRef input.")
        return TaskDataResult(status=1)

    body: dict = {}
    for field in ("title", "body", "state", "base"):
        val = getattr(input.params, field, "") or ""
        if val:
            body[field] = val

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}/pulls/{number}"
    try:
        response = await gh_request(
            "PATCH", url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.pulls.Update failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubPullRef",
        number=data["number"],
        html_url=data["html_url"],
        head=data["head"]["ref"],
        base=data["base"]["ref"],
        merged=data.get("merged", False),
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Updated PR #%d", data["number"])
    return TaskDataResult(status=0, output=[item])


async def PullsMerge(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Merge a pull request; outputs a gh.GitHubPullRef with merged=True."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    number = _resolve_pull_number(input.inputs, input.params)
    if not number:
        ctxt.error("gh.pulls.Merge: PR number required via 'number' param or GitHubPullRef input.")
        return TaskDataResult(status=1)

    body: dict = {
        "merge_method": getattr(input.params, "merge_method", "merge") or "merge",
    }
    commit_title = getattr(input.params, "commit_title", "") or ""
    commit_msg = getattr(input.params, "commit_message", "") or ""
    if commit_title:
        body["commit_title"] = commit_title
    if commit_msg:
        body["commit_message"] = commit_msg

    url = (
        f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
        f"/pulls/{number}/merge"
    )
    try:
        response = await gh_request(
            "PUT", url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.pulls.Merge failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubPullRef",
        number=number,
        html_url=data.get("url", ""),
        head="",
        base="",
        merged=data.get("merged", True),
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Merged PR #%d", number)
    return TaskDataResult(status=0, output=[item])
