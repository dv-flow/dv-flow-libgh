"""
Unit tests for gh.pulls and gh.releases task families.
"""
import os
import pytest
import httpx
from unittest.mock import MagicMock

from dv_flow.libgh.pulls import PullsCreate, PullsUpdate, PullsMerge
from dv_flow.libgh.pulls_review import PullsReviewCreate
from dv_flow.libgh.releases import ReleasesCreate, ReleasesUpdate, ReleasesGet
from dv_flow.libgh.releases_asset import ReleasesAssetUpload


# ---- shared helpers (copied/trimmed from test_issues.py) -------------------

def _make_item(type_name, **kwargs):
    item = MagicMock()
    item.type = type_name
    for k, v in kwargs.items():
        setattr(item, k, v)
    return item

def _make_auth_item(token="test-token"):
    return _make_item("gh.GitHubAuth", token=token, auth_type="pat")

def _make_repo_item(owner="my-org", repo="my-repo"):
    return _make_item(
        "gh.GitHubRepoRef",
        owner=owner, repo=repo,
        api_base="https://api.github.com",
        api_version="2022-11-28",
        retry_limit=1, retry_backoff_ms=0,
    )

def _make_pull_item(number=7, html_url="https://github.com/my-org/my-repo/pull/7"):
    return _make_item("gh.GitHubPullRef", number=number, html_url=html_url,
                      owner="my-org", repo="my-repo", head="feat", base="main", merged=False)

def _make_release_item(release_id=99, tag_name="v1.0.0",
                       upload_url="https://uploads.github.com/releases/99/assets{?name,label}"):
    return _make_item("gh.GitHubReleaseRef", release_id=release_id, tag_name=tag_name,
                      html_url="https://github.com/my-org/my-repo/releases/tag/v1.0.0",
                      upload_url=upload_url, owner="my-org", repo="my-repo")

def _make_input(params_dict, items=None):
    inp = MagicMock()
    params = MagicMock()
    for k, v in params_dict.items():
        setattr(params, k, v)
    inp.params = params
    inp.inputs = items or []
    inp.name = "test-task"
    return inp

def _make_ctxt():
    ctxt = MagicMock()
    ctxt.env = {"GITHUB_TOKEN": "env-token"}
    def _mk(type_name, **kwargs):
        return _make_item(type_name, **kwargs)
    ctxt.mkDataItem.side_effect = _mk
    return ctxt


_PULL_RESPONSE = {
    "number": 7,
    "html_url": "https://github.com/my-org/my-repo/pull/7",
    "head": {"ref": "feat"},
    "base": {"ref": "main"},
    "merged": False,
}

_RELEASE_RESPONSE = {
    "id": 99,
    "tag_name": "v1.0.0",
    "html_url": "https://github.com/my-org/my-repo/releases/tag/v1.0.0",
    "upload_url": "https://uploads.github.com/releases/99/assets{?name,label}",
}

# ============================================================================
# gh.pulls.Create
# ============================================================================

@pytest.mark.asyncio
async def test_pulls_create_success(respx_mock):
    respx_mock.post("https://api.github.com/repos/my-org/my-repo/pulls").mock(
        return_value=httpx.Response(201, json=_PULL_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"title": "My PR", "head": "feat", "base": "main", "body": "", "draft": False},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await PullsCreate(ctxt, inp)
    assert result.status == 0
    ctxt.mkDataItem.assert_called_once()
    assert ctxt.mkDataItem.call_args[1]["number"] == 7


@pytest.mark.asyncio
async def test_pulls_create_missing_fields():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"title": "", "head": "feat", "base": "main", "body": "", "draft": False},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await PullsCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


# ============================================================================
# gh.pulls.Update
# ============================================================================

@pytest.mark.asyncio
async def test_pulls_update_from_item(respx_mock):
    respx_mock.patch("https://api.github.com/repos/my-org/my-repo/pulls/7").mock(
        return_value=httpx.Response(200, json=_PULL_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "title": "Updated", "body": "", "state": "", "base": ""},
        items=[_make_auth_item(), _make_repo_item(), _make_pull_item(number=7)],
    )
    result = await PullsUpdate(ctxt, inp)
    assert result.status == 0


@pytest.mark.asyncio
async def test_pulls_update_no_number():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "title": "X", "body": "", "state": "", "base": ""},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await PullsUpdate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


# ============================================================================
# gh.pulls.Merge
# ============================================================================

@pytest.mark.asyncio
async def test_pulls_merge_success(respx_mock):
    respx_mock.put("https://api.github.com/repos/my-org/my-repo/pulls/7/merge").mock(
        return_value=httpx.Response(200, json={"merged": True, "message": "PR merged", "url": "https://github.com/my-org/my-repo/pull/7"})
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "commit_title": "", "commit_message": "", "merge_method": "merge"},
        items=[_make_auth_item(), _make_repo_item(), _make_pull_item(number=7)],
    )
    result = await PullsMerge(ctxt, inp)
    assert result.status == 0
    assert ctxt.mkDataItem.call_args[1]["merged"] == True


@pytest.mark.asyncio
async def test_pulls_merge_no_number():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "commit_title": "", "commit_message": "", "merge_method": "merge"},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await PullsMerge(ctxt, inp)
    assert result.status == 1


# ============================================================================
# gh.pulls.review.Create
# ============================================================================

@pytest.mark.asyncio
async def test_pulls_review_create(respx_mock):
    respx_mock.post("https://api.github.com/repos/my-org/my-repo/pulls/7/reviews").mock(
        return_value=httpx.Response(200, json={
            "id": 55, "html_url": "https://github.com/my-org/my-repo/pull/7#pullrequestreview-55",
            "state": "APPROVED",
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "body": "LGTM", "event": "APPROVE", "commit_id": ""},
        items=[_make_auth_item(), _make_repo_item(), _make_pull_item(number=7)],
    )
    result = await PullsReviewCreate(ctxt, inp)
    assert result.status == 0
    assert ctxt.mkDataItem.call_args[1]["review_id"] == 55


# ============================================================================
# gh.releases.Create
# ============================================================================

@pytest.mark.asyncio
async def test_releases_create_success(respx_mock):
    respx_mock.post("https://api.github.com/repos/my-org/my-repo/releases").mock(
        return_value=httpx.Response(201, json=_RELEASE_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"tag_name": "v1.0.0", "name": "Release 1.0.0", "body": "",
         "draft": False, "prerelease": False, "target_commitish": "",
         "generate_release_notes": False},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await ReleasesCreate(ctxt, inp)
    assert result.status == 0
    assert ctxt.mkDataItem.call_args[1]["tag_name"] == "v1.0.0"


@pytest.mark.asyncio
async def test_releases_create_missing_tag():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"tag_name": "", "name": "", "body": "", "draft": False, "prerelease": False,
         "target_commitish": "", "generate_release_notes": False},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await ReleasesCreate(ctxt, inp)
    assert result.status == 1


# ============================================================================
# gh.releases.Update
# ============================================================================

@pytest.mark.asyncio
async def test_releases_update(respx_mock):
    respx_mock.patch("https://api.github.com/repos/my-org/my-repo/releases/99").mock(
        return_value=httpx.Response(200, json=_RELEASE_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"release_id": 0, "tag_name": "", "name": "Updated", "body": "",
         "draft": False, "prerelease": False},
        items=[_make_auth_item(), _make_repo_item(), _make_release_item(release_id=99)],
    )
    result = await ReleasesUpdate(ctxt, inp)
    assert result.status == 0


# ============================================================================
# gh.releases.Get
# ============================================================================

@pytest.mark.asyncio
async def test_releases_get(respx_mock):
    respx_mock.get("https://api.github.com/repos/my-org/my-repo/releases/tags/v1.0.0").mock(
        return_value=httpx.Response(200, json=_RELEASE_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"tag_name": "v1.0.0"},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await ReleasesGet(ctxt, inp)
    assert result.status == 0
    assert ctxt.mkDataItem.call_args[1]["release_id"] == 99


# ============================================================================
# gh.releases.asset.Upload
# ============================================================================

@pytest.mark.asyncio
async def test_releases_asset_upload(tmp_path, respx_mock):
    asset_file = tmp_path / "my-binary"
    asset_file.write_bytes(b"fake binary data")

    respx_mock.post("https://uploads.github.com/releases/99/assets").mock(
        return_value=httpx.Response(201, json={
            "id": 123,
            "name": "my-binary",
            "browser_download_url": "https://github.com/my-org/my-repo/releases/download/v1.0.0/my-binary",
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"path": str(asset_file), "name": "", "content_type": "application/octet-stream",
         "upload_url": ""},
        items=[_make_auth_item(), _make_release_item()],
    )
    result = await ReleasesAssetUpload(ctxt, inp)
    assert result.status == 0
    assert ctxt.mkDataItem.call_args[1]["asset_id"] == 123


@pytest.mark.asyncio
async def test_releases_asset_missing_path():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"path": "", "name": "", "content_type": "application/octet-stream", "upload_url": ""},
        items=[_make_auth_item(), _make_release_item()],
    )
    result = await ReleasesAssetUpload(ctxt, inp)
    assert result.status == 1


@pytest.mark.asyncio
async def test_releases_asset_missing_upload_url():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"path": "/nonexistent/file", "name": "", "content_type": "application/octet-stream",
         "upload_url": ""},
        items=[_make_auth_item()],  # no GitHubReleaseRef
    )
    result = await ReleasesAssetUpload(ctxt, inp)
    assert result.status == 1
