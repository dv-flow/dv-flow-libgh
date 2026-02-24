################
DV Flow LibGH
################

LibGH is a `DV Flow <https://dv-flow.github.io>`_ task library that exposes
the GitHub REST and GraphQL APIs as composable dataflow tasks under the ``gh``
package namespace.  Tasks communicate through typed *data items* that flow
between steps — authentication credentials, repository references, issue
numbers, artifact identifiers, etc. — so they can be chained together with
``needs:`` without repeating boilerplate.

.. contents::
    :depth: 2


Installation
============

.. code-block:: bash

    pip install dv-flow-libgh

Requires Python ≥ 3.9 and a DV Flow manager installation (``dv-flow-mgr``).


Authentication
==============

Tasks resolve a GitHub token in this priority order:

1. A ``gh.GitHubAuth`` data item flowing in from an upstream ``gh.Auth`` task.
2. The ``GITHUB_TOKEN`` environment variable.

.. code-block:: yaml

    tasks:
      - name: auth
        uses: gh.Auth
        # token from $GITHUB_TOKEN by default; override with:
        # with:
        #   token: ${{ env.MY_TOKEN }}

      - name: repo
        uses: gh.Repo
        needs: [auth]
        with:
          owner: my-org
          repo:  my-repo

.. note::
    Creating check runs (``gh.checks.*``) requires a GitHub App installation
    token.  Personal Access Tokens cannot write to the Checks API.


Data Types
==========

All types extend ``std.DataItem`` and flow between tasks automatically when
declared with ``consumes:`` in the receiving task.

+-------------------------------------+--------------------------------------------------------------+
| Type                                | Key Fields                                                   |
+=====================================+==============================================================+
| ``gh.GitHubAuth``                   | ``token``, ``auth_type``                                     |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubRepoRef``                | ``owner``, ``repo``, ``api_base``,                           |
|                                     | ``retry_limit``, ``retry_backoff_ms``                        |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubIssueRef``               | ``number``, ``html_url``, ``owner``, ``repo``                |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubCommentRef``             | ``comment_id``, ``html_url``                                 |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubPullRef``                | ``number``, ``html_url``, ``state``, ``merged``              |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubReviewRef``              | ``review_id``, ``state``, ``html_url``                       |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubReleaseRef``             | ``release_id``, ``tag_name``, ``html_url``, ``upload_url``   |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubReleaseAssetRef``        | ``asset_id``, ``name``, ``download_url``                     |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubDiscussionRef``          | ``discussion_id``, ``number``, ``url``                       |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubDiscussionCommentRef``   | ``comment_id``, ``url``                                      |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubWorkflowRunRef``         | ``run_id``, ``workflow_id``, ``name``, ``status``,           |
|                                     | ``conclusion``, ``html_url``                                 |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubArtifactRef``            | ``artifact_id``, ``name``, ``size_in_bytes``,                |
|                                     | ``archive_download_url``                                     |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubStatusRef``              | ``status_id``, ``state``, ``context``, ``html_url``          |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubDeploymentRef``          | ``deployment_id``, ``ref``, ``environment``, ``status``      |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubCheckRunRef``            | ``check_run_id``, ``name``, ``status``, ``conclusion``       |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubRepoInfo``               | ``repo_id``, ``full_name``, ``default_branch``,              |
|                                     | ``html_url``, ``private``, ``fork``                          |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubRequestMeta``            | ``etag``, ``rate_limit_remaining``,                          |
|                                     | ``rate_limit_reset``, ``response_status``                    |
+-------------------------------------+--------------------------------------------------------------+
| ``gh.GitHubGraphQLMeta``            | ``query``, ``variables_json``, ``response_json``             |
+-------------------------------------+--------------------------------------------------------------+


Task: gh.Auth
=============

Resolves a GitHub token and outputs a ``gh.GitHubAuth`` item consumed by all
downstream tasks.

Parameters
----------

* **token** – [Optional] Explicit token value.  Defaults to the
  ``GITHUB_TOKEN`` environment variable.
* **auth_type** – [Optional] Token type label (default: ``Bearer``).

Produces
--------

* ``gh.GitHubAuth``


Task: gh.Repo
=============

Binds repository coordinates and HTTP retry settings into a
``gh.GitHubRepoRef`` item consumed by all repo-scoped tasks.

Parameters
----------

* **owner** – [Required] GitHub organisation or user name.
* **repo** – [Required] Repository name.
* **api_base** – [Optional] GitHub API base URL (default:
  ``https://api.github.com``).  Override for GitHub Enterprise.
* **retry_limit** – [Optional] Maximum retry attempts (default: ``3``).
* **retry_backoff_ms** – [Optional] Initial back-off in milliseconds
  (default: ``500``).

Consumes
--------

* ``gh.GitHubAuth``

Produces
--------

* ``gh.GitHubRepoRef``


Package: gh.request — Escape Hatches
=====================================

Task: gh.request.Rest
---------------------

Sends an arbitrary REST request and outputs a ``gh.GitHubRequestMeta`` item
with response metadata.

Parameters
----------

* **method** – HTTP verb: ``GET``, ``POST``, ``PATCH``, ``PUT``, ``DELETE``.
* **endpoint** – Path relative to the API base, e.g. ``/repos/org/repo/traffic/views``.
* **body_json** – [Optional] JSON string to send as the request body.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef`` (optional)

Produces
--------

* ``gh.GitHubRequestMeta``


Task: gh.request.GraphQL
------------------------

Executes an arbitrary GraphQL query/mutation and outputs a
``gh.GitHubGraphQLMeta`` item containing the raw response.

Parameters
----------

* **query** – GraphQL query or mutation string.
* **variables** – [Optional] JSON object string of variables.

Consumes
--------

* ``gh.GitHubAuth``

Produces
--------

* ``gh.GitHubGraphQLMeta``


Package: gh.repos — Repository Management
==========================================

Task: gh.repos.Get
------------------

Fetches repository metadata and outputs a ``gh.GitHubRepoInfo`` item.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubRepoInfo``


Task: gh.repos.List
-------------------

Lists repositories for a user or organisation.

Parameters
----------

* **user** – [Optional] User login (list their repos).
* **org** – [Optional] Organisation name (list org repos).  One of
  ``user`` or ``org`` is required.
* **type** – [Optional] Filter: ``all``, ``public``, ``private``,
  ``forks``, ``sources``, ``member`` (default: ``all``).
* **per_page** – [Optional] Maximum results (default: ``30``).

Consumes
--------

* ``gh.GitHubAuth``

Produces
--------

* ``gh.GitHubRepoInfo`` (one per repository)


Task: gh.repos.Create
---------------------

Creates a new repository and outputs a ``gh.GitHubRepoInfo`` item.

Parameters
----------

* **name** – [Required] New repository name.
* **org** – [Optional] Create under this organisation (default: authenticated user).
* **private** – [Optional] Make the repository private (default: ``false``).
* **description** – [Optional] Repository description.
* **auto_init** – [Optional] Initialise with a README (default: ``false``).

Consumes
--------

* ``gh.GitHubAuth``

Produces
--------

* ``gh.GitHubRepoInfo``


Task: gh.repos.Update
---------------------

Updates repository settings and outputs an updated ``gh.GitHubRepoInfo``.

Parameters
----------

* **description** – [Optional] New description.
* **homepage** – [Optional] New homepage URL.
* **private** – [Optional] Change visibility.
* **default_branch** – [Optional] New default branch name.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubRepoInfo``


Package: gh.contents — File Read/Write
=======================================

Task: gh.contents.Get
---------------------

Reads a file from the repository and outputs its decoded content.

Parameters
----------

* **path** – [Required] File path within the repository.
* **ref** – [Optional] Branch, tag or SHA (default: default branch).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``std.DataItem`` with fields: ``path``, ``content``, ``sha``, ``html_url``


Task: gh.contents.Put
---------------------

Creates or updates a file in the repository.

Parameters
----------

* **path** – [Required] File path within the repository.
* **message** – [Required] Commit message.
* **content** – [Required] UTF-8 text content to write.
* **branch** – [Optional] Target branch (default: default branch).
* **sha** – [Optional] Blob SHA of the file being replaced (required when
  updating an existing file; omit when creating a new file).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``


Package: gh.issues — Issue Management
======================================

Task: gh.issues.Create
----------------------

Creates a new issue and outputs a ``gh.GitHubIssueRef``.

Parameters
----------

* **title** – [Required] Issue title.
* **body** – [Optional] Issue body (Markdown).
* **labels** – [Optional] List of label names.
* **assignees** – [Optional] List of usernames to assign.
* **milestone** – [Optional] Milestone number.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubIssueRef``

Example
-------

.. code-block:: yaml

    tasks:
      - name: issue
        uses: gh.issues.Create
        needs: [auth, repo]
        with:
          title: "Automated issue from CI"
          body:  "Something went wrong in build #42."
          labels: [bug, automated]


Task: gh.issues.Update
----------------------

Updates an existing issue.

Parameters
----------

* **number** – [Optional] Issue number.  Overrides any consumed
  ``gh.GitHubIssueRef``.
* **title**, **body**, **state**, **labels**, **assignees**, **milestone** –
  [Optional] Fields to update.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubIssueRef`` (optional)

Produces
--------

* ``gh.GitHubIssueRef``


Task: gh.issues.Close
---------------------

Closes an issue (shorthand for ``Update`` with ``state: closed``).

Parameters
----------

* **number** – [Optional] Issue number.  Overrides any consumed
  ``gh.GitHubIssueRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubIssueRef`` (optional)


Task: gh.issues.comment.Create
-------------------------------

Adds a comment to an issue.

Parameters
----------

* **body** – [Required] Comment body (Markdown).
* **number** – [Optional] Issue number.  Overrides any consumed
  ``gh.GitHubIssueRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubIssueRef`` (optional)

Produces
--------

* ``gh.GitHubCommentRef``


Package: gh.pulls — Pull Request Management
============================================

Task: gh.pulls.Create
---------------------

Opens a pull request and outputs a ``gh.GitHubPullRef``.

Parameters
----------

* **title** – [Required] PR title.
* **head** – [Required] Source branch.
* **base** – [Required] Target branch.
* **body** – [Optional] PR description (Markdown).
* **draft** – [Optional] Open as draft (default: ``false``).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubPullRef``


Task: gh.pulls.Update
---------------------

Updates a pull request.

Parameters
----------

* **number** – [Optional] PR number.  Overrides any consumed
  ``gh.GitHubPullRef``.
* **title**, **body**, **state**, **base** – [Optional] Fields to update.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubPullRef`` (optional)

Produces
--------

* ``gh.GitHubPullRef``


Task: gh.pulls.Merge
--------------------

Merges a pull request.

Parameters
----------

* **number** – [Optional] PR number.  Overrides any consumed
  ``gh.GitHubPullRef``.
* **commit_title**, **commit_message** – [Optional] Custom merge commit
  message.
* **merge_method** – [Optional] ``merge``, ``squash``, or ``rebase``
  (default: ``merge``).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubPullRef`` (optional)


Task: gh.pulls.review.Create
-----------------------------

Submits a review on a pull request.

Parameters
----------

* **number** – [Optional] PR number.  Overrides any consumed
  ``gh.GitHubPullRef``.
* **event** – [Required] ``APPROVE``, ``REQUEST_CHANGES``, or ``COMMENT``.
* **body** – [Optional] Review body.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubPullRef`` (optional)

Produces
--------

* ``gh.GitHubReviewRef``


Package: gh.releases — Release Management
==========================================

Task: gh.releases.Create
------------------------

Creates a GitHub release and outputs a ``gh.GitHubReleaseRef``.

Parameters
----------

* **tag_name** – [Required] Git tag for the release.
* **name** – [Optional] Release title.
* **body** – [Optional] Release notes (Markdown).
* **draft** – [Optional] Save as draft (default: ``false``).
* **prerelease** – [Optional] Mark as pre-release (default: ``false``).
* **target_commitish** – [Optional] Branch or SHA for the tag.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubReleaseRef``


Task: gh.releases.Update
------------------------

Updates a release and outputs an updated ``gh.GitHubReleaseRef``.

Parameters
----------

* **release_id** – [Optional] Release ID.  Overrides any consumed
  ``gh.GitHubReleaseRef``.
* **tag_name**, **name**, **body**, **draft**, **prerelease** – [Optional]
  Fields to update.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubReleaseRef`` (optional)

Produces
--------

* ``gh.GitHubReleaseRef``


Task: gh.releases.Get
---------------------

Fetches a release by tag and outputs a ``gh.GitHubReleaseRef``.

Parameters
----------

* **tag_name** – [Required] Tag name to look up.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubReleaseRef``


Task: gh.releases.asset.Upload
-------------------------------

Uploads a file as a release asset.

Parameters
----------

* **asset_path** – [Required] Local path of the file to upload.
* **asset_name** – [Optional] Name for the asset (defaults to filename).
* **content_type** – [Optional] MIME type (default:
  ``application/octet-stream``).
* **release_id** – [Optional] Release ID.  Overrides any consumed
  ``gh.GitHubReleaseRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubReleaseRef`` (optional)

Produces
--------

* ``gh.GitHubReleaseAssetRef``


Package: gh.discussions — GitHub Discussions (GraphQL)
=======================================================

All Discussions tasks use the GitHub GraphQL API.  The ``discussion_id``
fields are GraphQL node IDs (e.g. ``DIC_kwDO...``).

Task: gh.discussions.List
-------------------------

Lists discussions and outputs one ``gh.GitHubDiscussionRef`` per discussion.

Parameters
----------

* **category_id** – [Optional] Filter by GraphQL category node ID.
* **first** – [Optional] Maximum results (default: ``20``).
* **after** – [Optional] Cursor for pagination.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubDiscussionRef`` (one per discussion)


Task: gh.discussions.Create
---------------------------

Creates a discussion.

Parameters
----------

* **repository_id** – [Required] GraphQL node ID of the repository.
* **category_id** – [Required] GraphQL node ID of the discussion category.
* **title** – [Required] Discussion title.
* **body** – [Optional] Discussion body (Markdown).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubDiscussionRef``


Task: gh.discussions.Edit
-------------------------

Updates the title and/or body of an existing discussion.

Parameters
----------

* **discussion_id** – [Optional] GraphQL node ID.  Overrides any consumed
  ``gh.GitHubDiscussionRef``.
* **title** – [Optional] New title.
* **body** – [Optional] New body.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubDiscussionRef`` (optional)

Produces
--------

* ``gh.GitHubDiscussionRef``


Task: gh.discussions.Delete
---------------------------

Deletes a discussion.

Parameters
----------

* **discussion_id** – [Optional] GraphQL node ID.  Overrides any consumed
  ``gh.GitHubDiscussionRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubDiscussionRef`` (optional)


Task: gh.discussions.comment.Create
------------------------------------

Adds a comment to a discussion.

Parameters
----------

* **body** – [Required] Comment body (Markdown).
* **discussion_id** – [Optional] GraphQL node ID.  Overrides any consumed
  ``gh.GitHubDiscussionRef``.
* **reply_to_id** – [Optional] GraphQL node ID of a comment to reply to.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubDiscussionRef`` (optional)

Produces
--------

* ``gh.GitHubDiscussionCommentRef``


Task: gh.discussions.comment.Edit
----------------------------------

Updates the body of an existing discussion comment.

Parameters
----------

* **body** – [Required] New body (Markdown).
* **comment_id** – [Optional] GraphQL node ID.  Overrides any consumed
  ``gh.GitHubDiscussionCommentRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubDiscussionCommentRef`` (optional)

Produces
--------

* ``gh.GitHubDiscussionCommentRef``


Package: gh.actions — GitHub Actions
=====================================

Task: gh.actions.workflowrun.List
----------------------------------

Lists workflow runs and outputs one ``gh.GitHubWorkflowRunRef`` per run.

Parameters
----------

* **workflow_id** – [Optional] Workflow file name or numeric ID to filter by.
* **branch** – [Optional] Branch filter.
* **status** – [Optional] Status filter: ``queued``, ``in_progress``,
  ``completed``, etc.
* **per_page** – [Optional] Maximum results (default: ``30``).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubWorkflowRunRef`` (one per run)


Task: gh.actions.workflowrun.Get
---------------------------------

Fetches a single workflow run by ID.

Parameters
----------

* **run_id** – [Optional] Overrides any consumed ``gh.GitHubWorkflowRunRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubWorkflowRunRef`` (optional)

Produces
--------

* ``gh.GitHubWorkflowRunRef``


Task: gh.actions.workflowrun.Cancel
------------------------------------

Cancels a workflow run.

Parameters
----------

* **run_id** – [Optional] Overrides any consumed ``gh.GitHubWorkflowRunRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubWorkflowRunRef`` (optional)


Task: gh.actions.workflowrun.Rerun
------------------------------------

Re-runs a workflow run (or only its failed jobs).

Parameters
----------

* **run_id** – [Optional] Overrides any consumed ``gh.GitHubWorkflowRunRef``.
* **failed_only** – [Optional] When ``true``, only re-run failed jobs
  (default: ``false``).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubWorkflowRunRef`` (optional)


Task: gh.actions.artifacts.List
--------------------------------

Lists artifacts for a workflow run or the whole repository.

Parameters
----------

* **run_id** – [Optional] Limit to a specific run.  Overrides any consumed
  ``gh.GitHubWorkflowRunRef``.
* **name** – [Optional] Filter by artifact name.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubWorkflowRunRef`` (optional)

Produces
--------

* ``gh.GitHubArtifactRef`` (one per artifact)


Task: gh.actions.artifacts.Download
-------------------------------------

Downloads an artifact archive as ``artifact.zip`` in the task rundir.

Parameters
----------

* **artifact_id** – [Optional] Overrides any consumed
  ``gh.GitHubArtifactRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubArtifactRef`` (optional)


Task: gh.actions.artifacts.Delete
-----------------------------------

Deletes an artifact.

Parameters
----------

* **artifact_id** – [Optional] Overrides any consumed
  ``gh.GitHubArtifactRef``.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubArtifactRef`` (optional)


Package: gh.statuses — Commit Status Checks
============================================

Task: gh.statuses.Create
-------------------------

Creates or updates a commit status.

Parameters
----------

* **sha** – [Required] Commit SHA.
* **state** – [Required] ``error``, ``failure``, ``pending``, or
  ``success``.
* **context** – [Optional] Label identifying the check (default:
  ``default``).
* **description** – [Optional] Short description.
* **target_url** – [Optional] Link to more details.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubStatusRef``

Example
-------

.. code-block:: yaml

    tasks:
      - name: status
        uses: gh.statuses.Create
        needs: [auth, repo]
        with:
          sha:         ${{ env.HEAD_SHA }}
          state:       success
          context:     ci/lint
          description: Lint passed
          target_url:  https://ci.example.com/build/42


Package: gh.deployments — Deployment Management
================================================

Task: gh.deployments.Create
----------------------------

Creates a deployment and outputs a ``gh.GitHubDeploymentRef``.

Parameters
----------

* **ref** – [Required] Branch, tag, or SHA to deploy.
* **environment** – [Optional] Environment name (default: ``production``).
* **description** – [Optional] Deployment description.
* **auto_merge** – [Optional] Auto-merge the default branch into the ref
  (default: ``false``).
* **required_contexts** – [Optional] List of status contexts that must pass.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubDeploymentRef``


Task: gh.deployments.StatusCreate
-----------------------------------

Creates a deployment status.

Parameters
----------

* **deployment_id** – [Optional] Overrides any consumed
  ``gh.GitHubDeploymentRef``.
* **state** – [Required] ``error``, ``failure``, ``inactive``,
  ``in_progress``, ``queued``, ``pending``, or ``success``.
* **description**, **log_url**, **environment_url** – [Optional]

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubDeploymentRef`` (optional)

Produces
--------

* ``gh.GitHubDeploymentRef``

Example
-------

.. code-block:: yaml

    tasks:
      - name: deploy
        uses: gh.deployments.Create
        needs: [auth, repo]
        with:
          ref:         main
          environment: staging

      - name: deploy_status
        uses: gh.deployments.StatusCreate
        needs: [auth, repo, deploy]
        with:
          state:           success
          environment_url: https://staging.example.com


Package: gh.checks — GitHub Checks API
=======================================

.. note::
    The Checks API requires a **GitHub App installation token**.  Personal
    Access Tokens cannot create or update check runs.

Task: gh.checks.Create
-----------------------

Creates a check run.

Parameters
----------

* **name** – [Required] Check run name.
* **head_sha** – [Required] Commit SHA.
* **status** – [Optional] Initial status: ``queued``, ``in_progress``,
  ``completed`` (default: ``queued``).
* **conclusion** – [Optional] Required when ``status`` is ``completed``:
  ``success``, ``failure``, ``neutral``, ``cancelled``, ``skipped``,
  ``timed_out``, ``action_required``.
* **details_url** – [Optional] URL for more details.
* **title**, **summary** – [Optional] Output title and summary (Markdown).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``gh.GitHubCheckRunRef``


Task: gh.checks.Update
-----------------------

Updates a check run.

Parameters
----------

* **check_run_id** – [Optional] Overrides any consumed
  ``gh.GitHubCheckRunRef``.
* **status**, **conclusion**, **title**, **summary** – [Optional] Fields to
  update.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``
* ``gh.GitHubCheckRunRef`` (optional)

Produces
--------

* ``gh.GitHubCheckRunRef``


Package: gh.teams — Organisation Team Management
=================================================

Task: gh.teams.List
--------------------

Lists teams in a GitHub organisation.

Parameters
----------

* **org** – [Required] Organisation name.
* **per_page** – [Optional] Maximum results (default: ``30``).

Consumes
--------

* ``gh.GitHubAuth``

Produces
--------

* ``std.DataItem`` per team (fields: ``team_slug``, ``name``,
  ``description``, ``html_url``)


Task: gh.teams.AddMember
------------------------

Adds a user to a team.

Parameters
----------

* **org** – [Required] Organisation name.
* **team_slug** – [Required] Team slug.
* **username** – [Required] GitHub username.
* **role** – [Optional] ``member`` or ``maintainer`` (default: ``member``).

Consumes
--------

* ``gh.GitHubAuth``


Task: gh.teams.RemoveMember
----------------------------

Removes a user from a team.

Parameters
----------

* **org** – [Required] Organisation name.
* **team_slug** – [Required] Team slug.
* **username** – [Required] GitHub username.

Consumes
--------

* ``gh.GitHubAuth``


Package: gh.collaborators — Repository Collaborators
=====================================================

Task: gh.collaborators.List
-----------------------------

Lists collaborators for a repository.

Parameters
----------

* **permission** – [Optional] Filter by permission level: ``pull``,
  ``triage``, ``push``, ``maintain``, ``admin``.
* **per_page** – [Optional] Maximum results (default: ``30``).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``

Produces
--------

* ``std.DataItem`` per collaborator (fields: ``login``, ``html_url``,
  ``role_name``)


Task: gh.collaborators.Add
---------------------------

Adds a collaborator to a repository.

Parameters
----------

* **username** – [Required] GitHub username.
* **permission** – [Optional] ``pull``, ``triage``, ``push``, ``maintain``,
  ``admin`` (default: ``push``).

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``


Task: gh.collaborators.Remove
------------------------------

Removes a collaborator from a repository.

Parameters
----------

* **username** – [Required] GitHub username.

Consumes
--------

* ``gh.GitHubAuth``
* ``gh.GitHubRepoRef``


Retry & Rate-Limit Handling
============================

All REST tasks use bounded exponential back-off with jitter.

+---------------------+---------+
| Parameter           | Default |
+=====================+=========+
| ``retry_limit``     | 3       |
+---------------------+---------+
| ``retry_backoff_ms``| 500     |
+---------------------+---------+

Override per-flow via ``gh.Repo`` parameters::

    - name: repo
      uses: gh.Repo
      with:
        owner:            my-org
        repo:             my-repo
        retry_limit:      5
        retry_backoff_ms: 1000

On a ``403``/``429`` response with a ``Retry-After`` header the library
automatically sleeps for the indicated duration before retrying.


Development
===========

.. code-block:: bash

    # Install in editable mode with test extras
    pip install -e ".[test]"

    # Run unit tests (no network required — uses respx mock)
    pytest tests/unit/
