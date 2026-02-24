"""teams.py — pytask implementations for gh.teams.{List,AddMember,RemoveMember}."""
import logging
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt
from dv_flow.libgh.gh_client import GHRequestError, resolve_auth, gh_request, DEFAULT_API_BASE

_log = logging.getLogger(__name__)


async def TeamsList(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """List org teams; outputs one std.DataItem per team."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    org = getattr(input.params, "org", "") or ""
    if not org:
        ctxt.error("gh.teams.List: 'org' is required.")
        return TaskDataResult(status=1)

    per_page = getattr(input.params, "per_page", 30) or 30
    url = f"{DEFAULT_API_BASE}/orgs/{org}/teams?per_page={per_page}"
    try:
        response = await gh_request("GET", url, token)
    except GHRequestError as exc:
        ctxt.error(f"gh.teams.List failed: {exc}")
        return TaskDataResult(status=1)

    output = []
    for team in response.json():
        item = ctxt.mkDataItem(
            "std.DataItem",
            team_slug=team["slug"],
            name=team["name"],
            description=team.get("description") or "",
            html_url=team.get("html_url", ""),
        )
        output.append(item)

    _log.info("Listed %d teams in org '%s'", len(output), org)
    return TaskDataResult(status=0, output=output)


async def TeamsAddMember(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Add a user to a team."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    org = getattr(input.params, "org", "") or ""
    team_slug = getattr(input.params, "team_slug", "") or ""
    username = getattr(input.params, "username", "") or ""
    if not org or not team_slug or not username:
        ctxt.error("gh.teams.AddMember: 'org', 'team_slug', and 'username' are required.")
        return TaskDataResult(status=1)

    role = getattr(input.params, "role", "member") or "member"
    url = f"{DEFAULT_API_BASE}/orgs/{org}/teams/{team_slug}/memberships/{username}"
    try:
        await gh_request("PUT", url, token, json={"role": role})
    except GHRequestError as exc:
        ctxt.error(f"gh.teams.AddMember failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Added %s to team %s/%s as %s", username, org, team_slug, role)
    return TaskDataResult(status=0)


async def TeamsRemoveMember(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """Remove a user from a team."""
    try:
        token = resolve_auth(input.inputs, ctxt.env)
    except GHRequestError as exc:
        ctxt.error(str(exc))
        return TaskDataResult(status=1)

    org = getattr(input.params, "org", "") or ""
    team_slug = getattr(input.params, "team_slug", "") or ""
    username = getattr(input.params, "username", "") or ""
    if not org or not team_slug or not username:
        ctxt.error("gh.teams.RemoveMember: 'org', 'team_slug', and 'username' are required.")
        return TaskDataResult(status=1)

    url = f"{DEFAULT_API_BASE}/orgs/{org}/teams/{team_slug}/memberships/{username}"
    try:
        await gh_request("DELETE", url, token)
    except GHRequestError as exc:
        ctxt.error(f"gh.teams.RemoveMember failed: {exc}")
        return TaskDataResult(status=1)

    _log.info("Removed %s from team %s/%s", username, org, team_slug)
    return TaskDataResult(status=0)
