# dv-flow-libgh — Implementation Status

Last updated: 2026-02-24

## What Is Built

`dv-flow-libgh` is a DV Flow task library that exposes the GitHub REST and
GraphQL APIs as composable dataflow tasks under the `gh` package namespace.

### Implemented Packages and Tasks

| Package | Tasks | Notes |
|---------|-------|-------|
| `gh` | `Auth`, `Repo` | Core setup; produces `GitHubAuth`, `GitHubRepoRef` |
| `gh.request` | `Rest`, `GraphQL` | Escape hatches for arbitrary calls |
| `gh.repos` | `Get`, `List`, `Create`, `Update` | Produces `GitHubRepoInfo` |
| `gh.contents` | `Get`, `Put` | Base64 decode/encode handled internally |
| `gh.issues` | `Create`, `Update`, `Close` | |
| `gh.issues.comment` | `Create` | |
| `gh.pulls` | `Create`, `Update`, `Merge` | |
| `gh.pulls.review` | `Create` | |
| `gh.releases` | `Create`, `Update`, `Get` | |
| `gh.releases.asset` | `Upload` | Strips `{?name,label}` template from upload URL |
| `gh.discussions` | `List`, `Create`, `Edit`, `Delete` | GraphQL-backed |
| `gh.discussions.comment` | `Create`, `Edit` | GraphQL-backed |
| `gh.actions.workflowrun` | `List`, `Get`, `Cancel`, `Rerun` | |
| `gh.actions.artifacts` | `List`, `Download`, `Delete` | Upload not in REST API |
| `gh.statuses` | `Create` | Commit status checks |
| `gh.deployments` | `Create`, `StatusCreate` | |
| `gh.checks` | `Create`, `Update` | Requires GitHub App token |
| `gh.teams` | `List`, `AddMember`, `RemoveMember` | Org-level |
| `gh.collaborators` | `List`, `Add`, `Remove` | Repo-level |

### Implemented Data Types (`flow.dv`)

All extend `std.DataItem`:

- `GitHubAuth` — token + auth_type
- `GitHubRepoRef` — owner, repo, api_base, api_version, retry_limit, retry_backoff_ms
- `GitHubIssueRef` — number, html_url, owner, repo
- `GitHubCommentRef` — comment_id, html_url
- `GitHubPullRef` — number, html_url, state, merged, owner, repo
- `GitHubReviewRef` — review_id, state, html_url
- `GitHubReleaseRef` — release_id, tag_name, html_url, upload_url
- `GitHubReleaseAssetRef` — asset_id, name, download_url
- `GitHubDiscussionRef` — discussion_id, number, url, owner, repo
- `GitHubDiscussionCommentRef` — comment_id, url
- `GitHubWorkflowRunRef` — run_id, workflow_id, name, status, conclusion, html_url
- `GitHubArtifactRef` — artifact_id, name, size_in_bytes, archive_download_url
- `GitHubStatusRef` — status_id, state, context, html_url
- `GitHubDeploymentRef` — deployment_id, ref, environment, status, url
- `GitHubCheckRunRef` — check_run_id, name, status, conclusion, html_url
- `GitHubRepoInfo` — repo_id, full_name, default_branch, html_url, private, fork
- `GitHubRequestMeta` — etag, rate_limit_remaining, rate_limit_reset, response_status
- `GitHubGraphQLMeta` — query, variables_json, response_json

### Infrastructure

- `gh_client.py` — `gh_request()` with retry/backoff/jitter, `resolve_auth()`, `resolve_repo()`
- `gh_graphql.py` — `gql_request()` with same retry pattern
- Rate-limit: `Retry-After` header respected on 403/429
- `X-GitHub-Api-Version: 2022-11-28` sent on all requests
- `docs/` — Sphinx documentation (conf.py, index.rst, Makefile)
- `.github/workflows/ci.yml` — uses `dv-flow/dv-flow-release/.github/workflows/dv-flow-pybuild.yml@main`

### Tests

49 unit tests, all passing (`pytest-asyncio` + `respx` mocks, no network required):

- `tests/unit/test_issues.py` — 24 tests
- `tests/unit/test_pulls_releases.py` — 14 tests
- `tests/unit/test_discussions.py` — 11 tests

## What Is Not Yet Built

### Known Gaps vs Original Design

| Item | Notes |
|------|-------|
| Pagination (`Link` header / cursor) | List tasks return only the first page. A `fetch_all` param + Link-header following would improve usability. |
| Conditional GET (`ETag`/`If-None-Match`) | `gh_client.py` plumbing exists (`GitHubRequestMeta.etag`) but tasks don't pass stored ETags on subsequent calls. |
| Unified poller task | "Wait until PR mergeable / workflow complete / deployment status" — useful but not implemented. |
| `gh.issues.List` / `gh.pulls.List` | Read-only list tasks were not added (only write/mutate tasks). Useful for dashboards and reports. |
| `gh.releases.List` | Same gap. |
| Dry-run mode | Mutation tasks could skip the API call and just log the intent. |
| Auth type gating | No early check that the token has the right scope/permission for the task (e.g., GitHub App for Checks). |
| Tests for gh.repos, gh.contents, gh.request | Files exist and are correct but unit tests were not written. |
| Tests for gh.actions, gh.statuses, gh.deployments, gh.checks, gh.teams, gh.collaborators | Same. |

### Original Design Items Not Pursued

- `gh.teams.Create`, `gh.teams.Update`, `gh.teams.AddRepo` — only `List/AddMember/RemoveMember` implemented.
- GraphQL Projects (new) support.
- Schema-driven task codegen.
- `pull_request.Review.Submit` as a separate task from `Review.Create`.

## Key Design Decisions (for reference)

- **Auth**: `GITHUB_TOKEN` env var default; overridable via `gh.GitHubAuth` data item flowing from `gh.Auth`.
- **HTTP client**: `httpx` (async).
- **Retry**: bounded exponential backoff + jitter via `retry_limit` / `retry_backoff_ms` on `gh.GitHubRepoRef`.
- **Package name**: `gh` (not `github`).
- **Discussions**: GraphQL only (REST does not support Discussions).
- **Checks API**: write requires GitHub App token; documented in task YAML and Sphinx docs.
- **Artifact upload**: not in the REST API; `gh.releases.asset.Upload` covers release assets only.

## Example: Weekly Activity Summary to Discussions

```yaml
package:
  name: weekly_report
  imports: [gh, std]

  with:
    owner: { type: str, value: my-org }
    repo:  { type: str, value: my-repo }
    category_id: { type: str, value: "<graphql-node-id>" }

  tasks:
  - name: auth
    uses: gh.Auth

  - name: repo
    uses: gh.Repo
    needs: [auth]
    with:
      owner: ${{ owner }}
      repo:  ${{ repo }}

  # ... fetch issues, PRs, runs (requires gh.issues.List etc. — not yet built) ...

  - name: post_discussion
    uses: gh.discussions.Create
    needs: [auth, repo]
    with:
      repository_id: "<repo-graphql-node-id>"
      category_id:   ${{ category_id }}
      title: "Weekly Summary"
      body:  "..."
```

> **Note**: `gh.issues.List`, `gh.pulls.List`, and `gh.releases.List` are not
> yet implemented; the example above would require them or use
> `gh.request.Rest` as an escape hatch.
