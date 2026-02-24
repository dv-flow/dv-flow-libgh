"""
actions_wfrun.py — pytask implementations for gh.actions.workflowrun.*.
"""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)
_WF_RUN_TYPE = "gh.GitHubWorkflowRunRef"


def _resolve_run_id(input_items, params):
    rid = getattr(params, "run_id", 0) or 0
    if rid:
        return rid
    for item in input_items:
        if getattr(item, "type", None) == _WF_RUN_TYPE:
            return getattr(item, "run_id", 0)
    return 0


def _run_item(ctxt, data, repo_info):
    return ctxt.mkDataItem(
        "gh.GitHubWorkflowRunRef",
        run_id=data["id"],
        workflow_id=data.get("workflow_id", 0),
        name=data.get("name", ""),
        status=data.get("status", ""),
        conclusion=data.get("conclusion") or "",
        html_url=data.get("html_url", ""),
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )


async def WorkflowRunList(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """List workflow runs; outputs one GitHubWorkflowRunRef per run."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    workflow_id = getattr(input.params, "workflow_id", "") or ""
    if workflow_id:
        url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
               f"/actions/workflows/{workflow_id}/runs")
    else:
        url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}/actions/runs"

    params = []
    branch = getattr(input.params, "branch", "") or ""
    if branch:
        params.append(f"branch={branch}")
    status = getattr(input.params, "status", "") or ""
    if status:
        params.append(f"status={status}")
    per_page = getattr(input.params, "per_page", 30) or 30
    params.append(f"per_page={per_page}")
    if params:
        url += "?" + "&".join(params)

    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.actions.workflowrun.List failed: {exc}")
        return TaskDataResult(status=1)

    runs = response.json().get("workflow_runs", [])
    output = [_run_item(ctxt, r, repo_info) for r in runs]
    _log.info("Listed %d workflow runs", len(output))
    return TaskDataResult(status=0, output=output)


async def WorkflowRunGet(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Fetch a workflow run by ID; outputs GitHubWorkflowRunRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    run_id = _resolve_run_id(input.inputs, input.params)
    if not run_id:
        ctxt.error("gh.actions.workflowrun.Get: run_id required.")
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/actions/runs/{run_id}")
    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.actions.workflowrun.Get failed: {exc}")
        return TaskDataResult(status=1)

    return TaskDataResult(status=0, output=[_run_item(ctxt, response.json(), repo_info)])


async def WorkflowRunCancel(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Cancel a workflow run."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    run_id = _resolve_run_id(input.inputs, input.params)
    if not run_id:
        ctxt.error("gh.actions.workflowrun.Cancel: run_id required.")
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/actions/runs/{run_id}/cancel")
    try:
        await gh_request("POST", url, token,
                         api_version=repo_info["api_version"],
                         retry_limit=repo_info["retry_limit"],
                         retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.actions.workflowrun.Cancel failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Cancelled workflow run %d", run_id)
    return TaskDataResult(status=0)


async def WorkflowRunRerun(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Re-run a workflow run (or its failed jobs only)."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    run_id = _resolve_run_id(input.inputs, input.params)
    if not run_id:
        ctxt.error("gh.actions.workflowrun.Rerun: run_id required.")
        return TaskDataResult(status=1)

    failed_only = getattr(input.params, "failed_only", False)
    suffix = "/rerun-failed-jobs" if failed_only else "/rerun"
    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/actions/runs/{run_id}{suffix}")
    try:
        await gh_request("POST", url, token,
                         api_version=repo_info["api_version"],
                         retry_limit=repo_info["retry_limit"],
                         retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.actions.workflowrun.Rerun failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Triggered rerun of workflow run %d (failed_only=%s)", run_id, failed_only)
    return TaskDataResult(status=0)
