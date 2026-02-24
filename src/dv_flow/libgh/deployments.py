"""deployments.py — pytask implementations for gh.deployments.{Create,StatusCreate}."""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)
_DEPLOY_TYPE = "gh.GitHubDeploymentRef"


def _resolve_deployment_id(input_items, params):
    did = getattr(params, "deployment_id", 0) or 0
    if did:
        return did
    for item in input_items:
        if getattr(item, "type", None) == _DEPLOY_TYPE:
            return getattr(item, "deployment_id", 0)
    return 0


async def DeploymentsCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a deployment; outputs gh.GitHubDeploymentRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    ref = getattr(input.params, "ref", "") or ""
    if not ref:
        ctxt.error("gh.deployments.Create: 'ref' is required.")
        return TaskDataResult(status=1)

    body: dict = {
        "ref": ref,
        "environment": getattr(input.params, "environment", "production") or "production",
        "auto_merge": bool(getattr(input.params, "auto_merge", False)),
    }
    desc = getattr(input.params, "description", "") or ""
    if desc:
        body["description"] = desc
    req_ctx = getattr(input.params, "required_contexts", None)
    if req_ctx is not None:
        body["required_contexts"] = list(req_ctx)

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}/deployments"
    try:
        response = await gh_request("POST", url, token,
                                    api_version=repo_info["api_version"],
                                    json=body,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.deployments.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubDeploymentRef",
        deployment_id=data["id"],
        ref=data.get("ref", ref),
        environment=data.get("environment", ""),
        status="pending",
        url=data.get("url", ""),
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Created deployment %d for %s → %s", data["id"], ref, body["environment"])
    return TaskDataResult(status=0, output=[item])


async def DeploymentsStatusCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a deployment status; outputs updated gh.GitHubDeploymentRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    deployment_id = _resolve_deployment_id(input.inputs, input.params)
    if not deployment_id:
        ctxt.error("gh.deployments.StatusCreate: deployment_id required.")
        return TaskDataResult(status=1)

    state = getattr(input.params, "state", "") or ""
    if not state:
        ctxt.error("gh.deployments.StatusCreate: 'state' is required.")
        return TaskDataResult(status=1)

    body: dict = {"state": state}
    for field in ("description", "log_url", "environment_url"):
        val = getattr(input.params, field, "") or ""
        if val:
            body[field] = val

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/deployments/{deployment_id}/statuses")
    try:
        await gh_request("POST", url, token,
                         api_version=repo_info["api_version"],
                         json=body,
                         retry_limit=repo_info["retry_limit"],
                         retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.deployments.StatusCreate failed: {exc}")
        return TaskDataResult(status=1)

    # Return updated ref with new status
    item = ctxt.mkDataItem(
        "gh.GitHubDeploymentRef",
        deployment_id=deployment_id,
        ref="", environment="", url="",
        status=state,
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Deployment %d status → %s", deployment_id, state)
    return TaskDataResult(status=0, output=[item])
