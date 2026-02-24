"""
Unit tests for dv-flow-libgh issues task family.

Uses pytest-httpx to mock the GitHub API without network access.
"""
import pytest
import pytest_asyncio
import httpx

from unittest.mock import MagicMock, AsyncMock
from dv_flow.libgh.gh_client import (
    GHRequestError,
    resolve_auth,
    resolve_repo,
    resolve_issue_ref,
    gh_request,
)
from dv_flow.libgh.gh_auth import Auth
from dv_flow.libgh.gh_repo import Repo
from dv_flow.libgh.issues import IssuesCreate, IssuesUpdate, IssuesClose
from dv_flow.libgh.issues_comment import IssuesCommentCreate


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def _make_item(type_name: str, **kwargs):
    """Create a minimal fake data item."""
    item = MagicMock()
    item.type = type_name
    for k, v in kwargs.items():
        setattr(item, k, v)
    return item


def _make_auth_item(token="test-token", auth_type="pat"):
    return _make_item("gh.GitHubAuth", token=token, auth_type=auth_type)


def _make_repo_item(owner="my-org", repo="my-repo"):
    return _make_item(
        "gh.GitHubRepoRef",
        owner=owner,
        repo=repo,
        api_base="https://api.github.com",
        api_version="2022-11-28",
        retry_limit=1,
        retry_backoff_ms=0,
    )


def _make_issue_item(number=42, html_url="https://github.com/my-org/my-repo/issues/42",
                     owner="my-org", repo="my-repo"):
    return _make_item("gh.GitHubIssueRef", number=number, html_url=html_url,
                      owner=owner, repo=repo)


def _make_input(params_dict: dict, items=None):
    """Build a fake TaskDataInput."""
    inp = MagicMock()
    params = MagicMock()
    for k, v in params_dict.items():
        setattr(params, k, v)
    inp.params = params
    inp.inputs = items or []
    inp.name = "test-task"
    return inp


def _make_ctxt():
    """Build a minimal fake TaskRunCtxt."""
    ctxt = MagicMock()
    ctxt.env = {"GITHUB_TOKEN": "env-token"}
    created_items = []

    def _mk(type_name, **kwargs):
        item = _make_item(type_name, **kwargs)
        created_items.append(item)
        return item

    ctxt.mkDataItem.side_effect = _mk
    ctxt._created_items = created_items
    return ctxt


# ---------------------------------------------------------------------------
# resolve_auth
# ---------------------------------------------------------------------------

def test_resolve_auth_from_item():
    items = [_make_auth_item(token="item-token")]
    assert resolve_auth(items) == "item-token"


def test_resolve_auth_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    assert resolve_auth([]) == "env-token"


def test_resolve_auth_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(GHRequestError, match="No GitHub token"):
        resolve_auth([])


def test_resolve_auth_prefers_item(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    items = [_make_auth_item(token="item-token")]
    assert resolve_auth(items) == "item-token"


# ---------------------------------------------------------------------------
# resolve_repo / resolve_issue_ref
# ---------------------------------------------------------------------------

def test_resolve_repo():
    items = [_make_repo_item()]
    info = resolve_repo(items)
    assert info["owner"] == "my-org"
    assert info["repo"] == "my-repo"


def test_resolve_repo_missing():
    with pytest.raises(GHRequestError, match="GitHubRepoRef"):
        resolve_repo([])


def test_resolve_issue_ref():
    items = [_make_issue_item(number=7)]
    ref = resolve_issue_ref(items)
    assert ref is not None
    assert ref["number"] == 7


def test_resolve_issue_ref_missing():
    assert resolve_issue_ref([]) is None


# ---------------------------------------------------------------------------
# gh_request — retry and error behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gh_request_success(respx_mock):
    respx_mock.post("https://api.github.com/repos/o/r/issues").mock(
        return_value=httpx.Response(201, json={"number": 1, "html_url": "https://github.com/o/r/issues/1"})
    )
    resp = await gh_request(
        "POST", "https://api.github.com/repos/o/r/issues",
        token="t", retry_limit=0,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_gh_request_retries_5xx(respx_mock):
    calls = []

    def side_effect(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(500, json={"message": "Server error"})
        return httpx.Response(201, json={"number": 2, "html_url": "https://x"})

    respx_mock.post("https://api.github.com/repos/o/r/issues").mock(side_effect=side_effect)
    resp = await gh_request(
        "POST", "https://api.github.com/repos/o/r/issues",
        token="t", retry_limit=3, retry_backoff_ms=0,
    )
    assert resp.status_code == 201
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_gh_request_raises_on_4xx(respx_mock):
    respx_mock.post("https://api.github.com/repos/o/r/issues").mock(
        return_value=httpx.Response(422, json={"message": "Validation Failed"})
    )
    with pytest.raises(GHRequestError, match="422"):
        await gh_request(
            "POST", "https://api.github.com/repos/o/r/issues",
            token="t", retry_limit=0,
        )


@pytest.mark.asyncio
async def test_gh_request_exhausts_retries(respx_mock):
    respx_mock.post("https://api.github.com/repos/o/r/issues").mock(
        return_value=httpx.Response(500, json={"message": "oops"})
    )
    with pytest.raises(GHRequestError):
        await gh_request(
            "POST", "https://api.github.com/repos/o/r/issues",
            token="t", retry_limit=2, retry_backoff_ms=0,
        )


# ---------------------------------------------------------------------------
# gh.Auth pytask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_from_env():
    ctxt = _make_ctxt()
    ctxt.env = {"GITHUB_TOKEN": "env-tok"}
    inp = _make_input({"token": "", "auth_type": "pat"})
    result = await Auth(ctxt, inp)
    assert result.status == 0
    assert len(result.output) == 1
    ctxt.mkDataItem.assert_called_once_with("gh.GitHubAuth", token="env-tok", auth_type="pat")


@pytest.mark.asyncio
async def test_auth_from_param():
    ctxt = _make_ctxt()
    ctxt.env = {}
    inp = _make_input({"token": "param-tok", "auth_type": "pat"})
    result = await Auth(ctxt, inp)
    assert result.status == 0
    ctxt.mkDataItem.assert_called_once_with("gh.GitHubAuth", token="param-tok", auth_type="pat")


@pytest.mark.asyncio
async def test_auth_no_token_fails(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    ctxt = _make_ctxt()
    ctxt.env = {}
    inp = _make_input({"token": "", "auth_type": "pat"})
    result = await Auth(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called_once()


# ---------------------------------------------------------------------------
# gh.issues.Create pytask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issues_create_success(respx_mock):
    respx_mock.post("https://api.github.com/repos/my-org/my-repo/issues").mock(
        return_value=httpx.Response(201, json={
            "number": 5, "html_url": "https://github.com/my-org/my-repo/issues/5"
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"title": "My Issue", "body": "Body text", "labels": [], "assignees": [], "milestone": 0},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await IssuesCreate(ctxt, inp)
    assert result.status == 0
    assert len(result.output) == 1
    ctxt.mkDataItem.assert_called_once_with(
        "gh.GitHubIssueRef",
        number=5,
        html_url="https://github.com/my-org/my-repo/issues/5",
        owner="my-org",
        repo="my-repo",
    )


@pytest.mark.asyncio
async def test_issues_create_missing_title():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"title": "", "body": "", "labels": [], "assignees": [], "milestone": 0},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await IssuesCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


@pytest.mark.asyncio
async def test_issues_create_api_error(respx_mock):
    respx_mock.post("https://api.github.com/repos/my-org/my-repo/issues").mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"title": "T", "body": "", "labels": [], "assignees": [], "milestone": 0},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await IssuesCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


# ---------------------------------------------------------------------------
# gh.issues.Update pytask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issues_update_from_item(respx_mock):
    respx_mock.patch("https://api.github.com/repos/my-org/my-repo/issues/42").mock(
        return_value=httpx.Response(200, json={
            "number": 42, "html_url": "https://github.com/my-org/my-repo/issues/42"
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "title": "Updated", "body": "", "labels": [], "assignees": [], "state": ""},
        items=[_make_auth_item(), _make_repo_item(), _make_issue_item(number=42)],
    )
    result = await IssuesUpdate(ctxt, inp)
    assert result.status == 0
    ctxt.mkDataItem.assert_called_once()
    args = ctxt.mkDataItem.call_args
    assert args[1]["number"] == 42


@pytest.mark.asyncio
async def test_issues_update_from_param(respx_mock):
    respx_mock.patch("https://api.github.com/repos/my-org/my-repo/issues/99").mock(
        return_value=httpx.Response(200, json={
            "number": 99, "html_url": "https://github.com/my-org/my-repo/issues/99"
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 99, "title": "Updated", "body": "", "labels": [], "assignees": [], "state": ""},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await IssuesUpdate(ctxt, inp)
    assert result.status == 0


@pytest.mark.asyncio
async def test_issues_update_no_number():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0, "title": "X", "body": "", "labels": [], "assignees": [], "state": ""},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await IssuesUpdate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


# ---------------------------------------------------------------------------
# gh.issues.Close pytask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issues_close(respx_mock):
    respx_mock.patch("https://api.github.com/repos/my-org/my-repo/issues/42").mock(
        return_value=httpx.Response(200, json={
            "number": 42, "html_url": "https://github.com/my-org/my-repo/issues/42",
            "state": "closed"
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"number": 0},
        items=[_make_auth_item(), _make_repo_item(), _make_issue_item(number=42)],
    )
    result = await IssuesClose(ctxt, inp)
    assert result.status == 0
    ctxt.mkDataItem.assert_called_once()


# ---------------------------------------------------------------------------
# gh.issues.comment.Create pytask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issues_comment_create(respx_mock):
    respx_mock.post("https://api.github.com/repos/my-org/my-repo/issues/42/comments").mock(
        return_value=httpx.Response(201, json={
            "id": 777, "html_url": "https://github.com/my-org/my-repo/issues/42#issuecomment-777"
        })
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"body": "Hello world", "issue_number": 0},
        items=[_make_auth_item(), _make_repo_item(), _make_issue_item(number=42)],
    )
    result = await IssuesCommentCreate(ctxt, inp)
    assert result.status == 0
    ctxt.mkDataItem.assert_called_once_with(
        "gh.GitHubCommentRef",
        comment_id=777,
        html_url="https://github.com/my-org/my-repo/issues/42#issuecomment-777",
    )


@pytest.mark.asyncio
async def test_issues_comment_missing_body():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"body": "", "issue_number": 0},
        items=[_make_auth_item(), _make_repo_item(), _make_issue_item(number=42)],
    )
    result = await IssuesCommentCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()
