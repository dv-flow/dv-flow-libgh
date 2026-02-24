"""
pulls_review.py — pytask implementation for gh.pulls.review.Create.
"""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError, resolve_auth, resolve_repo, gh_request,
)

_log = logging.getLogger(__name__)
_GH_PULL_TYPE = "gh.GitHubPullRef"


def _resolve_pull_number(input_items, params):
    number = getattr(params, "number", 0) or 0
    if number:
        return number
    for item in input_items:
        if getattr(item, "type", None) == _GH_PULL_TYPE:
            return getattr(item, "number", 0)
    return 0


async def PullsReviewCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a pull request review; outputs a gh.GitHubReviewRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    number = _resolve_pull_number(input.inputs, input.params)
    if not number:
        ctxt.error("gh.pulls.review.Create: PR number required via 'number' param or GitHubPullRef input.")
        return TaskDataResult(status=1)

    body: dict = {
        "event": getattr(input.params, "event", "COMMENT") or "COMMENT",
    }
    body_text = getattr(input.params, "body", "") or ""
    if body_text:
        body["body"] = body_text
    commit_id = getattr(input.params, "commit_id", "") or ""
    if commit_id:
        body["commit_id"] = commit_id

    url = (
        f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
        f"/pulls/{number}/reviews"
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
        ctxt.error(f"gh.pulls.review.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubReviewRef",
        review_id=data["id"],
        html_url=data.get("html_url", ""),
        state=data.get("state", ""),
    )
    _log.info("Created review %d on PR #%d (state=%s)", data["id"], number, data.get("state", ""))
    return TaskDataResult(status=0, output=[item])
