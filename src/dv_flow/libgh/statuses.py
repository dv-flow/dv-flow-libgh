"""statuses.py — pytask for gh.statuses.Create."""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)
_VALID_STATES = {"error", "failure", "pending", "success"}


async def StatusesCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a commit status; outputs gh.GitHubStatusRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    sha = getattr(input.params, "sha", "") or ""
    state = getattr(input.params, "state", "") or ""
    if not sha or not state:
        ctxt.error("gh.statuses.Create: 'sha' and 'state' are required.")
        return TaskDataResult(status=1)
    if state not in _VALID_STATES:
        ctxt.error(f"gh.statuses.Create: state must be one of {_VALID_STATES}, got '{state}'.")
        return TaskDataResult(status=1)

    body: dict = {"state": state, "context": getattr(input.params, "context", "default") or "default"}
    desc = getattr(input.params, "description", "") or ""
    if desc:
        body["description"] = desc
    target_url = getattr(input.params, "target_url", "") or ""
    if target_url:
        body["target_url"] = target_url

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/statuses/{sha}")
    try:
        response = await gh_request("POST", url, token,
                                    api_version=repo_info["api_version"],
                                    json=body,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.statuses.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubStatusRef",
        status_id=data["id"],
        state=data["state"],
        context=data.get("context", ""),
        html_url=data.get("url", ""),
    )
    _log.info("Created commit status %s on %s", state, sha[:8])
    return TaskDataResult(status=0, output=[item])
