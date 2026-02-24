# dv-flow-libgh

**DV Flow task library for GitHub REST and GraphQL APIs.**

Exposes a `gh` package namespace of composable dataflow tasks that wrap the
GitHub API, following the same structural pattern as other DV Flow libraries
(flow.dv YAML declarations + Python pytask implementations).

## Installation

```bash
pip install dv-flow-libgh
```

Requires Python ≥ 3.9 and a DV Flow manager installation (`dv-flow-mgr`).

## Authentication

Tasks resolve a GitHub token in this priority order:

1. A `gh.GitHubAuth` data item flowing in from an upstream `gh.Auth` task.
2. The `GITHUB_TOKEN` environment variable.

```yaml
# Set token at the top of your flow
tasks:
  - name: auth
    uses: gh.Auth
    # token from $GITHUB_TOKEN env var by default; override with:
    # with:
    #   token: ${{ env.MY_TOKEN }}

  - name: repo
    uses: gh.Repo
    needs: [auth]
    with:
      owner: my-org
      repo:  my-repo
```

> **Note:** Creating check runs (`gh.checks.*`) requires a GitHub App
> installation token — PATs cannot write to the Checks API.

## Package Overview

| Package | Tasks | Notes |
|---------|-------|-------|
| `gh` | `Auth`, `Repo` | Core setup |
| `gh.request` | `Rest`, `GraphQL` | Escape hatches |
| `gh.repos` | `Get`, `List`, `Create`, `Update` | Repository management |
| `gh.contents` | `Get`, `Put` | File read/write |
| `gh.issues` | `Create`, `Update`, `Close` | Issue management |
| `gh.issues.comment` | `Create` | Issue comments |
| `gh.pulls` | `Create`, `Update`, `Merge` | Pull request management |
| `gh.pulls.review` | `Create` | PR reviews |
| `gh.releases` | `Create`, `Update`, `Get` | Release management |
| `gh.releases.asset` | `Upload` | Release asset uploads |
| `gh.discussions` | `List`, `Create`, `Edit`, `Delete` | GitHub Discussions (GraphQL) |
| `gh.discussions.comment` | `Create`, `Edit` | Discussion comments (GraphQL) |
| `gh.actions.workflowrun` | `List`, `Get`, `Cancel`, `Rerun` | Workflow run control |
| `gh.actions.artifacts` | `List`, `Download`, `Delete` | CI artifacts |
| `gh.statuses` | `Create` | Commit status checks |
| `gh.deployments` | `Create`, `StatusCreate` | Deployment management |
| `gh.checks` | `Create`, `Update` | GitHub Checks API (App token required) |
| `gh.teams` | `List`, `AddMember`, `RemoveMember` | Org team management |
| `gh.collaborators` | `List`, `Add`, `Remove` | Repo collaborator management |

## Data Types

All types extend `std.DataItem` and flow between tasks.

| Type | Key Fields |
|------|-----------|
| `gh.GitHubAuth` | `token`, `auth_type` |
| `gh.GitHubRepoRef` | `owner`, `repo`, `api_base`, `retry_limit`, `retry_backoff_ms` |
| `gh.GitHubIssueRef` | `number`, `html_url`, `owner`, `repo` |
| `gh.GitHubCommentRef` | `comment_id`, `html_url` |
| `gh.GitHubPullRef` | `number`, `html_url`, `state`, `merged`, `owner`, `repo` |
| `gh.GitHubReviewRef` | `review_id`, `state`, `html_url` |
| `gh.GitHubReleaseRef` | `release_id`, `tag_name`, `html_url`, `upload_url` |
| `gh.GitHubReleaseAssetRef` | `asset_id`, `name`, `download_url` |
| `gh.GitHubDiscussionRef` | `discussion_id`, `number`, `url`, `owner`, `repo` |
| `gh.GitHubDiscussionCommentRef` | `comment_id`, `url` |
| `gh.GitHubWorkflowRunRef` | `run_id`, `workflow_id`, `name`, `status`, `conclusion`, `html_url` |
| `gh.GitHubArtifactRef` | `artifact_id`, `name`, `size_in_bytes`, `archive_download_url` |
| `gh.GitHubStatusRef` | `status_id`, `state`, `context`, `html_url` |
| `gh.GitHubDeploymentRef` | `deployment_id`, `ref`, `environment`, `status`, `url` |
| `gh.GitHubCheckRunRef` | `check_run_id`, `name`, `status`, `conclusion`, `html_url` |
| `gh.GitHubRepoInfo` | `repo_id`, `full_name`, `default_branch`, `html_url`, `private`, `fork` |
| `gh.GitHubRequestMeta` | `etag`, `rate_limit_remaining`, `rate_limit_reset`, `response_status` |
| `gh.GitHubGraphQLMeta` | `query`, `variables_json`, `response_json` |

## Examples

### Create a GitHub Issue

```yaml
imports:
  - name: gh
  - name: gh.issues

tasks:
  - name: auth
    uses: gh.Auth

  - name: repo
    uses: gh.Repo
    needs: [auth]
    with:
      owner: my-org
      repo:  my-repo

  - name: new_issue
    uses: gh.issues.Create
    needs: [auth, repo]
    with:
      title: "Automated issue from CI"
      body:  "Something went wrong in build #42."
      labels: [bug, automated]
```

### Open a Pull Request

```yaml
  - name: pr
    uses: gh.pulls.Create
    needs: [auth, repo]
    with:
      title: "Fix: update dependencies"
      head:  feature/update-deps
      base:  main
      body:  "Bumps all transitive deps."
```

### Set a Commit Status

```yaml
  - name: status
    uses: gh.statuses.Create
    needs: [auth, repo]
    with:
      sha:         ${{ env.HEAD_SHA }}
      state:       success
      context:     ci/lint
      description: Lint passed
      target_url:  https://ci.example.com/build/42
```

### Create a Deployment

```yaml
  - name: deploy
    uses: gh.deployments.Create
    needs: [auth, repo]
    with:
      ref:         main
      environment: production

  - name: deploy_status
    uses: gh.deployments.StatusCreate
    needs: [auth, repo, deploy]
    with:
      state: success
      environment_url: https://example.com
```

### Raw REST Escape Hatch

```yaml
imports:
  - name: gh
  - name: gh.request

tasks:
  - name: auth
    uses: gh.Auth
  - name: raw
    uses: gh.request.Rest
    needs: [auth]
    with:
      method:   GET
      endpoint: /repos/my-org/my-repo/traffic/views
```

### Raw GraphQL Escape Hatch

```yaml
  - name: gql
    uses: gh.request.GraphQL
    needs: [auth]
    with:
      query: |
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) { stargazerCount }
        }
      variables: '{"owner": "my-org", "name": "my-repo"}'
```

## Retry & Rate-Limit Handling

All REST tasks use bounded exponential back-off with jitter. Defaults:

| Parameter | Default |
|-----------|---------|
| `retry_limit` | 3 |
| `retry_backoff_ms` | 500 |

Override per-flow via `gh.Repo` with-parameters:

```yaml
  - name: repo
    uses: gh.Repo
    with:
      owner:            my-org
      repo:             my-repo
      retry_limit:      5
      retry_backoff_ms: 1000
```

On a `403`/`429` response with a `Retry-After` header, the library automatically
sleeps for the indicated duration before retrying.

## Development

```bash
# Install in editable mode with test extras
pip install -e ".[test]"

# Run unit tests (no network required — uses respx mock)
pytest tests/unit/
```
