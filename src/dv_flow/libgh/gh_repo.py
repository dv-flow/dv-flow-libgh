"""gh_repo.py — pytask implementation for gh.Repo."""
from dv_flow.mgr import TaskDataResult, TaskDataInput, TaskRunCtxt


async def Repo(ctxt: TaskRunCtxt, input: TaskDataInput) -> TaskDataResult:
    """
    Produce a gh.GitHubRepoRef data item from task parameters.
    """
    owner = getattr(input.params, "owner", "") or ""
    repo = getattr(input.params, "repo", "") or ""

    if not owner or not repo:
        ctxt.error("gh.Repo: 'owner' and 'repo' parameters are required.")
        return TaskDataResult(status=1)

    item = ctxt.mkDataItem(
        "gh.GitHubRepoRef",
        owner=owner,
        repo=repo,
        api_base=getattr(input.params, "api_base", "https://api.github.com"),
        api_version=getattr(input.params, "api_version", "2022-11-28"),
        retry_limit=getattr(input.params, "retry_limit", 3),
        retry_backoff_ms=getattr(input.params, "retry_backoff_ms", 500),
    )
    return TaskDataResult(status=0, output=[item])
