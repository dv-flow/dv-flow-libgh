"""checks.py — pytask implementations for gh.checks.{Create,Update}."""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)
_CHECK_TYPE = "gh.GitHubCheckRunRef"


def _resolve_check_run_id(input_items, params):
    cid = getattr(params, "check_run_id", 0) or 0
    if cid:
        return cid
    for item in input_items:
        if getattr(item, "type", None) == _CHECK_TYPE:
            return getattr(item, "check_run_id", 0)
    return 0


def _check_item(ctxt, data):
    return ctxt.mkDataItem(
        "gh.GitHubCheckRunRef",
        check_run_id=data["id"],
        name=data["name"],
        status=data.get("status", ""),
        conclusion=data.get("conclusion") or "",
        html_url=data.get("html_url", ""),
    )


async def ChecksCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a check run; outputs gh.GitHubCheckRunRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    name = getattr(input.params, "name", "") or ""
    head_sha = getattr(input.params, "head_sha", "") or ""
    if not name or not head_sha:
        ctxt.error("gh.checks.Create: 'name' and 'head_sha' are required.")
        return TaskDataResult(status=1)

    body: dict = {
        "name": name,
        "head_sha": head_sha,
        "status": getattr(input.params, "status", "queued") or "queued",
    }
    conclusion = getattr(input.params, "conclusion", "") or ""
    if conclusion:
        body["conclusion"] = conclusion
    details_url = getattr(input.params, "details_url", "") or ""
    if details_url:
        body["details_url"] = details_url
    title = getattr(input.params, "title", "") or ""
    summary = getattr(input.params, "summary", "") or ""
    if title or summary:
        body["output"] = {"title": title or name, "summary": summary}

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}/check-runs"
    try:
        response = await gh_request("POST", url, token,
                                    api_version=repo_info["api_version"],
                                    json=body,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.checks.Create failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Created check run '%s' on %s", name, head_sha[:8])
    return TaskDataResult(status=0, output=[_check_item(ctxt, response.json())])


async def ChecksUpdate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update a check run; outputs updated gh.GitHubCheckRunRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    check_run_id = _resolve_check_run_id(input.inputs, input.params)
    if not check_run_id:
        ctxt.error("gh.checks.Update: check_run_id required.")
        return TaskDataResult(status=1)

    body: dict = {}
    for field in ("status", "conclusion"):
        val = getattr(input.params, field, "") or ""
        if val:
            body[field] = val
    title = getattr(input.params, "title", "") or ""
    summary = getattr(input.params, "summary", "") or ""
    if title or summary:
        body["output"] = {"title": title, "summary": summary}

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/check-runs/{check_run_id}")
    try:
        response = await gh_request("PATCH", url, token,
                                    api_version=repo_info["api_version"],
                                    json=body,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.checks.Update failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Updated check run %d", check_run_id)
    return TaskDataResult(status=0, output=[_check_item(ctxt, response.json())])
