"""
contents.py — pytask implementations for gh.contents.{Get,Put}.
"""
import base64
import logging
import os
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo, gh_request

_log = logging.getLogger(__name__)


async def ContentsGet(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Read a file from the repo; writes content files and outputs GitHubRequestMeta."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    path = getattr(input.params, "path", "") or ""
    if not path:
        ctxt.error("gh.contents.Get: 'path' is required.")
        return TaskDataResult(status=1)

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/contents/{path.lstrip('/')}")
    ref = getattr(input.params, "ref", "") or ""

    # Pass ref as query param via a workaround: encode in URL
    if ref:
        url += f"?ref={ref}"

    try:
        response = await gh_request("GET", url, token,
                                    api_version=repo_info["api_version"],
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.contents.Get failed: {exc}")
        return TaskDataResult(status=1)

    data = response.json()
    # Write base64 content and decoded text
    b64 = data.get("content", "").replace("\n", "")
    with open(os.path.join(ctxt.rundir, "content.b64"), "w") as fh:
        fh.write(b64)
    try:
        decoded = base64.b64decode(b64).decode("utf-8")
        with open(os.path.join(ctxt.rundir, "content.txt"), "w") as fh:
            fh.write(decoded)
    except Exception:
        pass  # Binary content – skip text decode

    meta = ctxt.mkDataItem(
        "gh.GitHubRequestMeta",
        etag=response.headers.get("ETag", ""),
        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", -1)),
        rate_limit_reset=int(response.headers.get("X-RateLimit-Reset", 0)),
        response_status=response.status_code,
    )
    _log.info("Read %s (sha=%s)", path, data.get("sha", ""))
    return TaskDataResult(status=0, output=[meta])


async def ContentsPut(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create or update a file in the repo; outputs GitHubRequestMeta."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    path = getattr(input.params, "path", "") or ""
    message = getattr(input.params, "message", "") or ""
    if not path or not message:
        ctxt.error("gh.contents.Put: 'path' and 'message' are required.")
        return TaskDataResult(status=1)

    content = getattr(input.params, "content", "") or ""
    content_b64 = getattr(input.params, "content_b64", "") or ""
    if content and not content_b64:
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    if not content_b64:
        ctxt.error("gh.contents.Put: 'content' or 'content_b64' is required.")
        return TaskDataResult(status=1)

    body: dict = {"message": message, "content": content_b64}
    sha = getattr(input.params, "sha", "") or ""
    if sha:
        body["sha"] = sha
    branch = getattr(input.params, "branch", "") or ""
    if branch:
        body["branch"] = branch

    url = (f"{repo_info['api_base']}/repos/{repo_info['owner']}/{repo_info['repo']}"
           f"/contents/{path.lstrip('/')}")
    try:
        response = await gh_request("PUT", url, token,
                                    api_version=repo_info["api_version"],
                                    json=body,
                                    retry_limit=repo_info["retry_limit"],
                                    retry_backoff_ms=repo_info["retry_backoff_ms"])
    except GHRequestError as exc:
        ctxt.error(f"gh.contents.Put failed: {exc}")
        return TaskDataResult(status=1)

    meta = ctxt.mkDataItem(
        "gh.GitHubRequestMeta",
        etag=response.headers.get("ETag", ""),
        rate_limit_remaining=int(response.headers.get("X-RateLimit-Remaining", -1)),
        rate_limit_reset=int(response.headers.get("X-RateLimit-Reset", 0)),
        response_status=response.status_code,
    )
    _log.info("Wrote %s", path)
    return TaskDataResult(status=0, output=[meta])
