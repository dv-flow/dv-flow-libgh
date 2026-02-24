"""gh_auth.py — pytask implementation for gh.Auth."""
import os
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt


async def Auth(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """
    Produce a gh.GitHubAuth data item.

    Token resolution order:
    1. ``with.token`` parameter (if non-empty).
    2. ``GITHUB_TOKEN`` environment variable.
    """
    token = getattr(input.params, "token", "") or ""
    auth_type = getattr(input.params, "auth_type", "pat") or "pat"

    if not token:
        token = ctxt.env.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))

    if not token:
        ctxt.error(
            "gh.Auth: no token found. Set the GITHUB_TOKEN environment variable "
            "or provide it via the 'token' parameter."
        )
        return TaskDataResult(status=1)

    item = ctxt.mkDataItem("gh.GitHubAuth", token=token, auth_type=auth_type)
    return TaskDataResult(status=0, output=[item])
