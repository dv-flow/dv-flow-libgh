"""
actions_artifacts.py — pytask implementations for gh.actions.artifacts.*.
"""
import logging
import os
import httpx
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError, resolve_auth, resolve_repo, gh_request, _build_headers, DEFAULT_API_VERSION,
)

_log = logging.getLogger(__name__)
_ARTIFACT_TYPE = "gh.GitHubArtifactRef"
_WF_RUN_TYPE = "gh.GitHubWorkflowRunRef"


def _resolve_artifact_id(input_items, params):
    aid = getattr(params, "artifact_id", 0) or 0
    if aid:
        return aid
    for item in input_items:
        if getattr(item, "type", None) == _ARTIFACT_TYPE:
            return getattr(item, "artifact_id", 0)
    return 0


def _resolve_run_id(input_items, params):
    rid = getattr(params, "run_id", 0) or 0
    if rid:
        return rid
    for item in input_items:
        if getattr(item, "type", None) == _WF_RUN_TYPE:
            return getattr(item, "run_id", 0)
    return 0


def _artifact_item(ctxt, data):
    return ctxt.mkDataItem(
        "gh.GitHubArtifactRef",
        artifact_id=data["id"],
        name=data["name"],
        size_in_bytes=data.get("size_in_bytes", 0),
        archive_download_url=data.get("archive_download_url", ""),
        expired=data.get("expired", False),
    )


async def ArtifactsList(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """List artifacts; outputs one GitHubArtifactRef per artifact."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    run_id = _resolve_run_id(input.inputs, input.params)
    if run_id:
        url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
               f"/actions/runs/{run_id}/artifacts")
    else:
        url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
               f"/actions/artifacts")

    name_filter = getattr(input.params, "name", "") or ""
    if name_filter:
        url += f"?name={name_filter}"

    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.actions.artifacts.List failed: {exc}")
        return TaskDataResult(status=1)

    artifacts = response.json().get("artifacts", [])
    output = [_artifact_item(ctxt, a) for a in artifacts]
    _log.info("Listed %d artifacts", len(output))
    return TaskDataResult(status=0, output=output)


async def ArtifactsDownload(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Download an artifact archive to artifact.zip in the rundir."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    artifact_id = _resolve_artifact_id(input.inputs, input.params)
    if not artifact_id:
        ctxt.error("gh.actions.artifacts.Download: artifact_id required.")
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/actions/artifacts/{artifact_id}/zip")
    headers = _build_headers(token, repo_info.get("api_version", DEFAULT_API_VERSION))

    out_path = os.path.join(ctxt.rundir, "artifact.zip")
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with client.stream("GET", url, headers=headers) as response:
            if response.status_code >= 300:
                ctxt.error(f"gh.actions.artifacts.Download failed: HTTP {response.status_code}")
                return TaskDataResult(status=1)
            with open(out_path, "wb") as fh:
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)

    _log.info("Downloaded artifact %d to %s", artifact_id, out_path)
    return TaskDataResult(status=0)


async def ArtifactsDelete(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Delete an artifact."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    artifact_id = _resolve_artifact_id(input.inputs, input.params)
    if not artifact_id:
        ctxt.error("gh.actions.artifacts.Delete: artifact_id required.")
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/actions/artifacts/{artifact_id}")
    try:
        await gh_request("DELETE", url, token,
                         api_version=repo_info["api_version"],
                         retry_limit=repo_info["retry_limit"],
                         retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.actions.artifacts.Delete failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Deleted artifact %d", artifact_id)
    return TaskDataResult(status=0)
