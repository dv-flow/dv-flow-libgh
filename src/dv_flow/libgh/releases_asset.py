"""
releases_asset.py — pytask for gh.releases.asset.Upload.
"""
import logging
import os
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import (
    GHRequestError, resolve_auth, _build_headers,
    DEFAULT_API_VERSION,
)
import httpx

_log = logging.getLogger(__name__)
_GH_RELEASE_TYPE = "gh.GitHubReleaseRef"


def _resolve_upload_url(input_items, params):
    url = getattr(params, "upload_url", "") or ""
    if url:
        return url
    for item in input_items:
        if getattr(item, "type", None) == _GH_RELEASE_TYPE:
            return getattr(item, "upload_url", "")
    return ""


async def ReleasesAssetUpload(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Upload a release asset; outputs a gh.GitHubReleaseAssetRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    file_path = getattr(input.params, "path", "") or ""
    if not file_path:
        ctxt.error("gh.releases.asset.Upload: 'path' parameter is required.")
        return TaskDataResult(status=1)
    if not os.path.isfile(file_path):
        ctxt.error(f"gh.releases.asset.Upload: file not found: {file_path}")
        return TaskDataResult(status=1)

    upload_url = _resolve_upload_url(input.inputs, input.params)
    if not upload_url:
        ctxt.error(
            "gh.releases.asset.Upload: upload_url not found. "
            "Add a gh.releases.Create/Get task as a dependency."
        )
        return TaskDataResult(status=1)

    # Strip the template suffix GitHub adds to upload URLs: {?name,label}
    upload_url = upload_url.split("{")[0]

    asset_name = getattr(input.params, "name", "") or os.path.basename(file_path)
    content_type = getattr(input.params, "content_type", "application/octet-stream") or "application/octet-stream"

    # Determine api_version from consumed GitHubReleaseRef (best-effort)
    api_version = DEFAULT_API_VERSION
    for item in input.inputs:
        if getattr(item, "type", None) == _GH_RELEASE_TYPE:
            api_version = DEFAULT_API_VERSION  # not carried on ReleaseRef
            break

    headers = _build_headers(token, api_version)
    headers["Content-Type"] = content_type

    with open(file_path, "rb") as fh:
        file_data = fh.read()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            upload_url,
            headers=headers,
            content=file_data,
            params={"name": asset_name},
        )

    if response.status_code >= 300:
        ctxt.error(f"gh.releases.asset.Upload failed: HTTP {response.status_code}: {response.text}")
        return TaskDataResult(status=1)

    data = response.json()
    item = ctxt.mkDataItem(
        "gh.GitHubReleaseAssetRef",
        asset_id=data["id"],
        name=data["name"],
        browser_download_url=data.get("browser_download_url", ""),
    )
    _log.info("Uploaded asset %s (id=%d)", data["name"], data["id"])
    return TaskDataResult(status=0, output=[item])
