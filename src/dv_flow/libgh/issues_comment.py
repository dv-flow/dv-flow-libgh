"""
issues_comment.py — pytask implementation for gh.issues.comment.Create.
"""
import logging

from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError,
    resolve_auth,
    resolve_repo,
    resolve_issue_ref,
    gh_request,
)

_log = logging.getLogger(__name__)


async def IssuesCommentCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Add a comment to a GitHub issue; outputs a gh.GitHubCommentRef data item."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    # Resolve issue number: param overrides data item
    number = getattr(input.params, "issue_number", 0) or 0
    if not number:
        ref = resolve_issue_ref(input.inputs)
        if ref:
            number = ref["number"]
    if not number:
        ctxt.error(
            "gh.issues.comment.Create: issue number required via 'issue_number' param "
            "or gh.GitHubIssueRef input."
        )
        return TaskDataResult(status=1)

    body_text = getattr(input.params, "body", "") or ""
    if not body_text:
        ctxt.error("gh.issues.comment.Create: 'body' parameter is required.")
        return TaskDataResult(status=1)

    url = (
        f"{repo_info['api_base']}/repos/"
        f"{repo_info['owner']}/{repo_info['repo']}/issues/{number}/comments"
    )

    try:
        response = await gh_request(
            "POST", url, token,
            api_version=repo_info["api_version"],
            json={"body": body_text},
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.issues.comment.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubCommentRef",
        comment_id=data["id"],
        html_url=data["html_url"],
    )
    _log.info("Created comment %d on issue #%d", data["id"], number)
    return TaskDataResult(status=0, output=[item])
