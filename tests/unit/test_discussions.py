"""
Unit tests for gh.discussions task family.
"""
import pytest
import httpx
from unittest.mock import MagicMock

from dv_flow.libgh.discussions import DiscussionsList, DiscussionsCreate
from dv_flow.libgh.discussions_comment import DiscussionsCommentCreate
from dv_flow.libgh.gh_graphql import gql_request
from dv_flow.libgh.gh_client import GHRequestError


# ---- helpers ---------------------------------------------------------------

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

def _make_disc_item(discussion_id="D_1", number=3, url="https://github.com/my-org/my-repo/discussions/3"):
    return _make_item("gh.GitHubDiscussionRef", discussion_id=discussion_id,
                      number=number, url=url, owner="my-org", repo="my-repo")

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


_GQL_ENDPOINT = "https://api.github.com/graphql"

_LIST_RESPONSE = {
    "data": {
        "repository": {
            "discussions": {
                "nodes": [
                    {"id": "D_1", "number": 1, "url": "https://github.com/my-org/my-repo/discussions/1"},
                    {"id": "D_2", "number": 2, "url": "https://github.com/my-org/my-repo/discussions/2"},
                ],
                "pageInfo": {"endCursor": "Y3Vyc29y", "hasNextPage": False},
            }
        }
    }
}

_CREATE_RESPONSE = {
    "data": {
        "createDiscussion": {
            "discussion": {
                "id": "D_3",
                "number": 3,
                "url": "https://github.com/my-org/my-repo/discussions/3",
            }
        }
    }
}

_COMMENT_RESPONSE = {
    "data": {
        "addDiscussionComment": {
            "comment": {
                "id": "DC_1",
                "url": "https://github.com/my-org/my-repo/discussions/3#discussioncomment-1",
            }
        }
    }
}


# ============================================================================
# gql_request helper
# ============================================================================

@pytest.mark.asyncio
async def test_gql_request_success(respx_mock):
    respx_mock.post(_GQL_ENDPOINT).mock(
        return_value=httpx.Response(200, json={"data": {"hello": "world"}})
    )
    result = await gql_request("token", "{ hello }")
    assert result == {"hello": "world"}


@pytest.mark.asyncio
async def test_gql_request_graphql_error(respx_mock):
    respx_mock.post(_GQL_ENDPOINT).mock(
        return_value=httpx.Response(200, json={
            "errors": [{"message": "Could not resolve to a node"}]
        })
    )
    with pytest.raises(GHRequestError, match="GraphQL error"):
        await gql_request("token", "{ bad_query }")


@pytest.mark.asyncio
async def test_gql_request_retries_5xx(respx_mock):
    calls = []
    def side_effect(request):
        calls.append(request)
        if len(calls) < 2:
            return httpx.Response(500, json={"message": "server error"})
        return httpx.Response(200, json={"data": {"ok": True}})

    respx_mock.post(_GQL_ENDPOINT).mock(side_effect=side_effect)
    result = await gql_request("token", "{ ok }", retry_limit=3, retry_backoff_ms=0)
    assert result == {"ok": True}
    assert len(calls) == 2


# ============================================================================
# gh.discussions.List
# ============================================================================

@pytest.mark.asyncio
async def test_discussions_list(respx_mock):
    respx_mock.post(_GQL_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_LIST_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"first": 20, "after": "", "category_id": ""},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await DiscussionsList(ctxt, inp)
    assert result.status == 0
    assert len(result.output) == 2
    assert ctxt.mkDataItem.call_count == 2
    first_call = ctxt.mkDataItem.call_args_list[0]
    assert first_call[1]["discussion_id"] == "D_1"
    assert first_call[1]["number"] == 1


@pytest.mark.asyncio
async def test_discussions_list_no_auth(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    ctxt = _make_ctxt()
    ctxt.env = {}
    inp = _make_input(
        {"first": 20, "after": "", "category_id": ""},
        items=[_make_repo_item()],
    )
    result = await DiscussionsList(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


# ============================================================================
# gh.discussions.Create
# ============================================================================

@pytest.mark.asyncio
async def test_discussions_create(respx_mock):
    respx_mock.post(_GQL_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_CREATE_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"repository_id": "R_kgDO", "category_id": "DIC_kwDO", "title": "Weekly Summary", "body": "Body text"},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await DiscussionsCreate(ctxt, inp)
    assert result.status == 0
    assert len(result.output) == 1
    assert ctxt.mkDataItem.call_args[1]["discussion_id"] == "D_3"
    assert ctxt.mkDataItem.call_args[1]["number"] == 3


@pytest.mark.asyncio
async def test_discussions_create_missing_fields():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"repository_id": "", "category_id": "DIC", "title": "T", "body": ""},
        items=[_make_auth_item(), _make_repo_item()],
    )
    result = await DiscussionsCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


# ============================================================================
# gh.discussions.comment.Create
# ============================================================================

@pytest.mark.asyncio
async def test_discussions_comment_create(respx_mock):
    respx_mock.post(_GQL_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_COMMENT_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"body": "Great discussion!", "discussion_id": "", "reply_to_id": ""},
        items=[_make_auth_item(), _make_disc_item(discussion_id="D_3")],
    )
    result = await DiscussionsCommentCreate(ctxt, inp)
    assert result.status == 0
    assert ctxt.mkDataItem.call_args[1]["comment_id"] == "DC_1"


@pytest.mark.asyncio
async def test_discussions_comment_from_param(respx_mock):
    respx_mock.post(_GQL_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_COMMENT_RESPONSE)
    )
    ctxt = _make_ctxt()
    inp = _make_input(
        {"body": "Hello", "discussion_id": "D_3", "reply_to_id": ""},
        items=[_make_auth_item()],  # no GitHubDiscussionRef item, uses param
    )
    result = await DiscussionsCommentCreate(ctxt, inp)
    assert result.status == 0


@pytest.mark.asyncio
async def test_discussions_comment_missing_body():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"body": "", "discussion_id": "D_3", "reply_to_id": ""},
        items=[_make_auth_item()],
    )
    result = await DiscussionsCommentCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()


@pytest.mark.asyncio
async def test_discussions_comment_missing_discussion_id():
    ctxt = _make_ctxt()
    inp = _make_input(
        {"body": "Hi", "discussion_id": "", "reply_to_id": ""},
        items=[_make_auth_item()],  # no disc ref, no param
    )
    result = await DiscussionsCommentCreate(ctxt, inp)
    assert result.status == 1
    ctxt.error.assert_called()
