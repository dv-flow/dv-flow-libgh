"""
repos.py — pytask implementations for gh.repos.{Get,List,Create,Update}.
"""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)


def _repo_item(ctxt, data):
    return ctxt.mkDataItem(
        "gh.GitHubRepoInfo",
        owner=data["owner"]["login"],
        repo=data["name"],
        repository_id=data.get("node_id", ""),
        default_branch=data.get("default_branch", ""),
        html_url=data.get("html_url", ""),
        private=data.get("private", False),
    )


async def ReposGet(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Fetch repo metadata; outputs gh.GitHubRepoInfo."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.repos.Get failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    _log.info("Got repo %s/%s (node_id=%s)", data["owner"]["login"], data["name"], data.get("node_id", ""))
    return TaskDataResult(status=0, output=[_repo_item(ctxt, data)])


async def ReposList(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """List repos; outputs one gh.GitHubRepoInfo per repo."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    org = getattr(input.params, "org", "") or ""
    per_page = getattr(input.params, "per_page", 30) or 30
    repo_type = getattr(input.params, "type", "all") or "all"

    if org:
        url = f"{repo_info['api_base']}/orgs/{org}/repos"
    else:
        url = f"{repo_info['api_base']}/user/repos"

    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    json=None,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.repos.List failed: {exc}")
        return TaskDataResult(status=1)

    output = [_repo_item(ctxt, r) for r in response.json()]
    _log.info("Listed %d repos", len(output))
    return TaskDataResult(status=0, output=output)


async def ReposCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a repo; outputs gh.GitHubRepoInfo."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    # Best-effort api_base from repo ref
    try:
        repo_info = resolve_repo(input.inputs)
        api_base = repo_info["api_base"]
        api_version = repo_info["api_version"]
        retry_limit = repo_info["retry_limit"]
        retry_backoff_ms = repo_info["retry_backoff_ms"]
    except GHRequestError:
        from dv_flow.libgh.gh_client import DEFAULT_API_BASE, DEFAULT_API_VERSION
        api_base, api_version, retry_limit, retry_backoff_ms = DEFAULT_API_BASE, DEFAULT_API_VERSION, 3, 500

    name = getattr(input.params, "name", "") or ""
    if not name:
        ctxt.error("gh.repos.Create: 'name' is required.")
        return TaskDataResult(status=1)

    org = getattr(input.params, "org", "") or ""
    url = f"{api_base}/orgs/{org}/repos" if org else f"{api_base}/user/repos"

    body: dict = {"name": name}
    desc = getattr(input.params, "description", "") or ""
    if desc:
        body["description"] = desc
    if getattr(input.params, "private", False):
        body["private"] = True
    if getattr(input.params, "auto_init", False):
        body["auto_init"] = True

    try:
        response = await gh_request("POST", url, token,
                                    api_version=api_version,
                                    json=body,
                                    retry_limit=retry_limit,
                                    retry_backoff_ms=retry_backoff_ms)
    except GHRequestError as exc:
        ctxt.error(f"gh.repos.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    _log.info("Created repo %s", data["full_name"])
    return TaskDataResult(status=0, output=[_repo_item(ctxt, data)])


async def ReposUpdate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update repo settings; outputs gh.GitHubRepoInfo."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    body: dict = {}
    for field in ("description", "homepage", "default_branch"):
        val = getattr(input.params, field, "") or ""
        if val:
            body[field] = val
    if getattr(input.params, "private", False):
        body["private"] = True

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
    try:
        response = await gh_request("PATCH", url, token,
                                    api_version=repo_info["api_version"],
                                    json=body,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.repos.Update failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    _log.info("Updated repo %s", data["full_name"])
    return TaskDataResult(status=0, output=[_repo_item(ctxt, data)])
