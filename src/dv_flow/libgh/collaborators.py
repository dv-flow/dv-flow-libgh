"""collaborators.py — pytask implementations for gh.collaborators.{List,Add,Remove}."""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)


async def CollaboratorsList(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """List repo collaborators; outputs one std.DataItem per collaborator."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/collaborators")
    permission = getattr(input.params, "permission", "") or ""
    params = []
    if permission:
        params.append(f"permission={permission}")
    per_page = getattr(input.params, "per_page", 30) or 30
    params.append(f"per_page={per_page}")
    url += "?" + "&".join(params)

    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.collaborators.List failed: {exc}")
        return TaskDataResult(status=1)

    output = []
    for user in response.json():
        item = ctxt.mkDataItem(
            "std.DataItem",
            login=user["login"],
            html_url=user.get("html_url", ""),
            role_name=user.get("role_name", ""),
        )
        output.append(item)

    _log.info("Listed %d collaborators for %s/%s", len(output), repo_info["owner"], repo_info["repo"])
    return TaskDataResult(status=0, output=output)


async def CollaboratorsAdd(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Add a collaborator to a repository."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    username = getattr(input.params, "username", "") or ""
    if not username:
        ctxt.error("gh.collaborators.Add: 'username' is required.")
        return TaskDataResult(status=1)

    permission = getattr(input.params, "permission", "push") or "push"
    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/collaborators/{username}")
    try:
        await gh_request("PUT", url, token,
                         api_version=repo_info["api_version"],
                         json={"permission": permission},
                         retry_limit=repo_info["retry_limit"],
                         retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.collaborators.Add failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Added %s as collaborator (%s) on %s/%s", username, permission,
              repo_info["owner"], repo_info["repo"])
    return TaskDataResult(status=0)


async def CollaboratorsRemove(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Remove a collaborator from a repository."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    username = getattr(input.params, "username", "") or ""
    if not username:
        ctxt.error("gh.collaborators.Remove: 'username' is required.")
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/collaborators/{username}")
    try:
        await gh_request("DELETE", url, token,
                         api_version=repo_info["api_version"],
                         retry_limit=repo_info["retry_limit"],
                         retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.collaborators.Remove failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Removed %s as collaborator from %s/%s", username,
              repo_info["owner"], repo_info["repo"])
    return TaskDataResult(status=0)
