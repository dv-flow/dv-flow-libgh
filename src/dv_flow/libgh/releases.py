"""
releases.py — pytask implementations for gh.releases.{Create,Update,Get}.
"""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError, resolve_auth, resolve_repo, gh_request,
)

_log = logging.getLogger(__name__)
_GH_RELEASE_TYPE = "gh.GitHubReleaseRef"


def _resolve_release_id(input_items, params):
    rid = getattr(params, "release_id", 0) or 0
    if rid:
        return rid
    for item in input_items:
        if getattr(item, "type", None) == _GH_RELEASE_TYPE:
            return getattr(item, "release_id", 0)
    return 0


def _release_item(ctxt, data, repo_info):
    return ctxt.mkDataItem(
        "gh.GitHubReleaseRef",
        release_id=data["id"],
        tag_name=data["tag_name"],
        html_url=data["html_url"],
        upload_url=data.get("upload_url", ""),
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )


async def ReleasesCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a release; outputs gh.GitHubReleaseRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    tag_name = getattr(input.params, "tag_name", "") or ""
    if not tag_name:
        ctxt.error("gh.releases.Create: 'tag_name' is required.")
        return TaskDataResult(status=1)

    body: dict = {"tag_name": tag_name}
    for field in ("name", "body", "target_commitish"):
        val = getattr(input.params, field, "") or ""
        if val:
            body[field] = val
    if getattr(input.params, "draft", False):
        body["draft"] = True
    if getattr(input.params, "prerelease", False):
        body["prerelease"] = True
    if getattr(input.params, "generate_release_notes", False):
        body["generate_release_notes"] = True

    url = f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}/releases"
    try:
        response = await gh_request(
            "POST", url, token,
            api_version=repo_info["api_version"],
            json=body,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.releases.Create failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    _log.info("Created release %s: %s", data["tag_name"], data["html_url"])
    return TaskDataResult(status=0, output=[_release_item(ctxt, data, repo_info)])


async def ReleasesUpdate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update a release; outputs gh.GitHubReleaseRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    release_id = _resolve_release_id(input.inputs, input.params)
    if not release_id:
        ctxt.error("gh.releases.Update: release_id required via param or GitHubReleaseRef input.")
        return TaskDataResult(status=1)

    body: dict = {}
    for field in ("tag_name", "name", "body"):
        val = getattr(input.params, field, "") or ""
        if val:
            body[field] = val
    # Include bool fields only when explicitly set to True
    if getattr(input.params, "draft", False):
        body["draft"] = True
    if getattr(input.params, "prerelease", False):
        body["prerelease"] = True

    url = (
        f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
        f"/releases/{release_id}"
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
        ctxt.error(f"gh.releases.Update failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    _log.info("Updated release %d", release_id)
    return TaskDataResult(status=0, output=[_release_item(ctxt, data, repo_info)])


async def ReleasesGet(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Fetch a release by tag; outputs gh.GitHubReleaseRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    tag_name = getattr(input.params, "tag_name", "") or ""
    if not tag_name:
        ctxt.error("gh.releases.Get: 'tag_name' is required.")
        return TaskDataResult(status=1)

    url = (
        f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
        f"/releases/tags/{tag_name}"
    )
    try:
        response = await gh_request(
            "GET", url, token,
            api_version=repo_info["api_version"],
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.releases.Get failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    _log.info("Got release %s (id=%d)", data["tag_name"], data["id"])
    return TaskDataResult(status=0, output=[_release_item(ctxt, data, repo_info)])
