"""
discussions.py — pytask implementations for gh.discussions.{List,Create,Edit,Delete}.

All GitHub Discussions operations require GraphQL (not REST).
"""
import logging
from typing import List as TList

from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, resolve_repo
from dv_flow.libgh.gh_graphql import gql_request

_log = logging.getLogger(__name__)

_LIST_QUERY = """
query($owner: String!, $repo: String!, $first: Int!, $after: String, $categoryId: ID) {
  repository(owner: $owner, name: $repo) {
    discussions(first: $first, after: $after, categoryId: $categoryId) {
      nodes {
        id
        number
        url
      }
      pageInfo {
        endCursor
        hasNextPage
      }
    }
  }
}
"""

_CREATE_MUTATION = """
mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {
    repositoryId: $repositoryId,
    categoryId: $categoryId,
    title: $title,
    body: $body
  }) {
    discussion {
      id
      number
      url
    }
  }
}
"""
_UPDATE_MUTATION = """
mutation($discussionId: ID!, $title: String, $body: String) {
  updateDiscussion(input: {
    discussionId: $discussionId,
    title: $title,
    body: $body
  }) {
    discussion {
      id
      number
      url
    }
  }
}
"""

_DELETE_MUTATION = """
mutation($id: ID!) {
  deleteDiscussion(input: { id: $id }) {
    discussion {
      id
    }
  }
}
"""

_DISCUSSION_TYPE = "gh.GitHubDiscussionRef"


def _resolve_discussion_id(input_items, params):
    did = getattr(params, "discussion_id", "") or ""
    if did:
        return did
    for item in input_items:
        if getattr(item, "type", None) == _DISCUSSION_TYPE:
            return getattr(item, "discussion_id", "")
    return ""


async def DiscussionsList(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """List discussions; outputs one gh.GitHubDiscussionRef per discussion."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    variables = {
        "owner": repo_info["owner"],
        "repo": repo_info["repo"],
        "first": getattr(input.params, "first", 20) or 20,
    }
    after = getattr(input.params, "after", "") or ""
    if after:
        variables["after"] = after
    category_id = getattr(input.params, "category_id", "") or ""
    if category_id:
        variables["categoryId"] = category_id

    try:
        data = await gql_request(
            token,
            _LIST_QUERY,
            variables,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.discussions.List failed: {exc}")
        return TaskDataResult(status=1)

    nodes = data.get("repository", {}).get("discussions", {}).get("nodes", [])
    output = []
    for node in nodes:
        item = ctxt.mkDataItem(
            "gh.GitHubDiscussionRef",
            discussion_id=node["id"],
            number=node["number"],
            url=node["url"],
            owner=repo_info["owner"],
            repo=repo_info["repo"],
        )
        output.append(item)

    _log.info("Listed %d discussions", len(output))
    return TaskDataResult(status=0, output=output)


async def DiscussionsCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Create a discussion; outputs a gh.GitHubDiscussionRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    repository_id = getattr(input.params, "repository_id", "") or ""
    category_id = getattr(input.params, "category_id", "") or ""
    title = getattr(input.params, "title", "") or ""

    if not repository_id or not category_id or not title:
        ctxt.error(
            "gh.discussions.Create: 'repository_id', 'category_id', and 'title' are required."
        )
        return TaskDataResult(status=1)

    variables = {
        "repositoryId": repository_id,
        "categoryId": category_id,
        "title": title,
        "body": getattr(input.params, "body", "") or "",
    }

    try:
        data = await gql_request(
            token,
            _CREATE_MUTATION,
            variables,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.discussions.Create failed: {exc}")
        return TaskDataResult(status=1)

    disc = data["createDiscussion"]["discussion"]
    item = ctxt.mkDataItem(
        "gh.GitHubDiscussionRef",
        discussion_id=disc["id"],
        number=disc["number"],
        url=disc["url"],
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Created discussion #%d: %s", disc["number"], disc["url"])
    return TaskDataResult(status=0, output=[item])


async def DiscussionsEdit(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update a discussion title/body; outputs updated gh.GitHubDiscussionRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    discussion_id = _resolve_discussion_id(input.inputs, input.params)
    if not discussion_id:
        ctxt.error("gh.discussions.Edit: discussion_id required.")
        return TaskDataResult(status=1)

    variables: dict = {"discussionId": discussion_id}
    title = getattr(input.params, "title", "") or ""
    body = getattr(input.params, "body", "") or ""
    if title:
        variables["title"] = title
    if body:
        variables["body"] = body

    try:
        data = await gql_request(
            token, _UPDATE_MUTATION, variables,
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.discussions.Edit failed: {exc}")
        return TaskDataResult(status=1)

    disc = data["updateDiscussion"]["discussion"]
    item = ctxt.mkDataItem(
        "gh.GitHubDiscussionRef",
        discussion_id=disc["id"],
        number=disc["number"],
        url=disc["url"],
        owner=repo_info["owner"],
        repo=repo_info["repo"],
    )
    _log.info("Updated discussion %s", discussion_id)
    return TaskDataResult(status=0, output=[item])


async def DiscussionsDelete(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Delete a discussion."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
        repo_info = resolve_repo(input.inputs)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    discussion_id = _resolve_discussion_id(input.inputs, input.params)
    if not discussion_id:
        ctxt.error("gh.discussions.Delete: discussion_id required.")
        return TaskDataResult(status=1)

    try:
        await gql_request(
            token, _DELETE_MUTATION, {"id": discussion_id},
            retry_limit=repo_info["retry_limit"],
            retry_backoff_ms=repo_info["retry_backoff_ms"],
        )
    except GHRequestError as exc:
        ctxt.error(f"gh.discussions.Delete failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Deleted discussion %s", discussion_id)
    return TaskDataResult(status=0)
