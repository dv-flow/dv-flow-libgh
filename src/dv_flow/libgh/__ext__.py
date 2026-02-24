import os

def dvfm_packages():
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    return {
        'gh':                              os.path.join(pkg_dir, 'flow.dv'),
        'gh.request':                      os.path.join(pkg_dir, 'request_flow.dv'),
        'gh.repos':                        os.path.join(pkg_dir, 'repos_flow.dv'),
        'gh.contents':                     os.path.join(pkg_dir, 'contents_flow.dv'),
        'gh.issues':                       os.path.join(pkg_dir, 'issues_flow.dv'),
        'gh.issues.comment':               os.path.join(pkg_dir, 'issues_comment_flow.dv'),
        'gh.pulls':                        os.path.join(pkg_dir, 'pulls_flow.dv'),
        'gh.pulls.review':                 os.path.join(pkg_dir, 'pulls_review_flow.dv'),
        'gh.releases':                     os.path.join(pkg_dir, 'releases_flow.dv'),
        'gh.releases.asset':               os.path.join(pkg_dir, 'releases_asset_flow.dv'),
        'gh.discussions':                  os.path.join(pkg_dir, 'discussions_flow.dv'),
        'gh.discussions.comment':          os.path.join(pkg_dir, 'discussions_comment_flow.dv'),
        'gh.actions.workflowrun':          os.path.join(pkg_dir, 'actions_wfrun_flow.dv'),
        'gh.actions.artifacts':            os.path.join(pkg_dir, 'actions_artifacts_flow.dv'),
        'gh.statuses':                     os.path.join(pkg_dir, 'statuses_flow.dv'),
        'gh.deployments':                  os.path.join(pkg_dir, 'deployments_flow.dv'),
        'gh.checks':                       os.path.join(pkg_dir, 'checks_flow.dv'),
        'gh.teams':                        os.path.join(pkg_dir, 'teams_flow.dv'),
        'gh.collaborators':                os.path.join(pkg_dir, 'collaborators_flow.dv'),
    }
