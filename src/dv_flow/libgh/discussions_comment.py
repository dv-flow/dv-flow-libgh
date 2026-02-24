"""
discussions_comment.py — pytask for gh.discussions.comment.{Create,Edit}.
"""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth
from dv_flow.libgh.gh_graphql import gql_request

_log = logging.getLogger(__name__)
_GH_DISC_TYPE = "gh.GitHubDiscussionRef"

_ADD_COMMENT_MUTATION = """
mutation($discussionId: ID!, $body: String!, $replyToId: ID) {
  addDiscussionComment(input: {
    discussionId: $discussionId,
    body: $body,
    replyToId: $replyToId
  }) {
    comment {
      id
      url
    }
  }
}
"""


_UPDATE_COMMENT_MUTATION = """
mutation($id: ID!, $body: String!) {
  updateDiscussionComment(input: { commentId: $id, body: $body }) {
    comment {
      id
      url
    }
  }
}
"""

_GH_DISC_COMMENT_TYPE = "gh.GitHubDiscussionCommentRef"


def _resolve_comment_id(input_items, params):
    cid = getattr(params, "comment_id", "") or ""
    if cid:
        return cid
    for item in input_items:
        if getattr(item, "type", None) == _GH_DISC_COMMENT_TYPE:
            return getattr(item, "comment_id", "")
    return ""


async def DiscussionsCommentEdit(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Update a discussion comment body; outputs updated gh.GitHubDiscussionCommentRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    comment_id = _resolve_comment_id(input.inputs, input.params)
    if not comment_id:
        ctxt.error("gh.discussions.comment.Edit: comment_id required.")
        return TaskDataResult(status=1)

    body_text = getattr(input.params, "body", "") or ""
    if not body_text:
        ctxt.error("gh.discussions.comment.Edit: 'body' is required.")
        return TaskDataResult(status=1)

    try:
        data = await gql_request(token, _UPDATE_COMMENT_MUTATION, {"id": comment_id, "body": body_text})
    except GHRequestError as exc:
        ctxt.error(f"gh.discussions.comment.Edit failed: {exc}")
        return TaskDataResult(status=1)

    comment = data["updateDiscussionComment"]["comment"]
    item = ctxt.mkDataItem(
        "gh.GitHubDiscussionCommentRef",
        comment_id=comment["id"],
        url=comment["url"],
    )
    _log.info("Updated discussion comment: %s", comment["url"])
    return TaskDataResult(status=0, output=[item])


def _resolve_discussion_id(input_items, params):
    did = getattr(params, "discussion_id", "") or ""
    if did:
        return did
    for item in input_items:
        if getattr(item, "type", None) == _GH_DISC_TYPE:
            return getattr(item, "discussion_id", "")
    return ""


async def DiscussionsCommentCreate(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Add a comment to a discussion; outputs a gh.GitHubDiscussionCommentRef."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    discussion_id = _resolve_discussion_id(input.inputs, input.params)
    if not discussion_id:
        ctxt.error(
            "gh.discussions.comment.Create: discussion_id required via 'discussion_id' param "
            "or gh.GitHubDiscussionRef input."
        )
        return TaskDataResult(status=1)

    body_text = getattr(input.params, "body", "") or ""
    if not body_text:
        ctxt.error("gh.discussions.comment.Create: 'body' is required.")
        return TaskDataResult(status=1)

    variables: dict = {"discussionId": discussion_id, "body": body_text}
    reply_to = getattr(input.params, "reply_to_id", "") or ""
    if reply_to:
        variables["replyToId"] = reply_to

    try:
        data = await gql_request(token, _ADD_COMMENT_MUTATION, variables)
    except GHRequestError as exc:
        ctxt.error(f"gh.discussions.comment.Create failed: {exc}")
        return TaskDataResult(status=1)

    comment = data["addDiscussionComment"]["comment"]
    item = ctxt.mkDataItem(
        "gh.GitHubDiscussionCommentRef",
        comment_id=comment["id"],
        url=comment["url"],
    )
    _log.info("Created discussion comment: %s", comment["url"])
    return TaskDataResult(status=0, output=[item])
