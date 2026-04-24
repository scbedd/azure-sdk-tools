# Handle Status Checks Pipeline — Implementation Plan

## Problem

`check-enforcer` (GitHub Action) is being retired. The repo needs a replacement that enforces "no triggered check can fail" as a single required branch protection rule.

## Approach

Create a new pipeline — `Handle Status Checks` — that lives in the **`azure-sdk/internal`** AzDO project and is triggered via **pipeline completion triggers** (`resources.pipelines`) pointing at the **`public`** project's PR-triggered pipelines.

Because the pipeline runs in `internal`, it can use `login-to-github.yml` to obtain an authenticated `GH_TOKEN` (via the `AzureSDKEngKeyVault Secrets` service connection). That token is used to query the GitHub Checks API for the triggering commit's check runs.

The job:
1. Calls `login-to-github.yml` to populate `GH_TOKEN`
2. Queries GitHub Checks API for all check runs on the triggering PR commit SHA
3. Filters out itself (`Handle Status Checks`)
4. Exits 1 if any other check is in-progress, queued, or failed — AzDO posts failure to GitHub automatically
5. Exits 0 if all others are complete and green — AzDO posts success to GitHub automatically

`Handle Status Checks` becomes the single required check in GitHub branch protection. No GitHub API write is needed.

---

## Files to Create / Modify

### 1. `eng/pipelines/handle-status-checks.yml` *(new file)*

```yaml
trigger: none
pr: none

resources:
  pipelines:
  - pipeline: test-proxy
    project: public
    source: 'azure-sdk-tools - test-proxy'   # AzDO pipeline display name (definitionId 2892)
    trigger: true
  - pipeline: pipeline-generator
    project: public
    source: 'azure-sdk-tools - pipeline-generator'   # definitionId 641
    trigger: true
  # ... one entry per PR-triggered ci.yml in the repo (see pipeline list below)

variables:
  GITHUB_REPO: 'Azure/azure-sdk-tools'

jobs:
- job: HandleStatusChecks
  displayName: 'Handle Status Checks'
  pool:
    vmImage: ubuntu-latest
  steps:
  - template: /eng/common/pipelines/templates/steps/login-to-github.yml
    parameters:
      TokenOwners:
        - Azure

  - bash: |
      SHA="$(resources.pipeline.triggering.sourceCommit)"

      RESPONSE=$(curl -s \
        -H "Authorization: token $(GH_TOKEN)" \
        -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$(GITHUB_REPO)/commits/${SHA}/check-runs?per_page=100")

      BLOCKING=$(echo "$RESPONSE" | jq '[.check_runs[] |
        select(.name != "Handle Status Checks") |
        select(
          .status == "in_progress" or
          .status == "queued" or
          (.status == "completed" and (
            .conclusion == "failure" or
            .conclusion == "timed_out" or
            .conclusion == "cancelled" or
            .conclusion == "action_required"
          ))
        )] | length')

      if [ "$BLOCKING" -gt 0 ]; then
        echo "##[error]$BLOCKING check(s) are still in-progress or failed."
        exit 1
      fi

      echo "All other checks passed or were skipped."
    displayName: 'Evaluate PR check statuses'
    env:
      GH_TOKEN: $(GH_TOKEN)
```

**Key design notes:**
- Pipeline lives in **`internal`** project so it can access `AzureSDKEngKeyVault Secrets` service connection used by `login-to-github.yml`
- `project: public` in each `resources.pipelines` entry points the trigger at the upstream public project pipelines
- `login-to-github.yml` populates `GH_TOKEN` — authenticated calls get 5000 req/hr vs 60 unauthenticated
- `trigger: none` + `pr: none` — fires ONLY via pipeline completion trigger
- `resources.pipeline.<alias>.sourceCommit` provides the PR commit SHA
- Self-exclusion by check name `"Handle Status Checks"` — must match exactly what AzDO reports to GitHub
- `queued` and `in_progress` are treated as blocking — prevents false-success race where this fires before other PR checks have started

---

### 2. Full Pipeline List

Every ci.yml with a `pr:` trigger needs a `resources.pipelines` entry with `project: public`.

**Action before writing final YAML:** grep all `ci.yml` files for `pr:` triggers to build the complete list, then confirm each pipeline's AzDO display name in the `public` project.

Known so far:

| YAML file | AzDO definition ID | AzDO display name (to confirm) |
|---|---|---|
| tools/test-proxy/ci.yml | 2892 | TBD |
| tools/pipeline-generator/ci.yml | 641 | TBD |
| (all others with `pr:` triggers) | TBD | TBD |

---

### 3. Register the pipeline in AzDO *(one-time manual step)*

1. In `azure-sdk/internal` project, create a new pipeline pointing at `eng/pipelines/handle-status-checks.yml`
2. Name it exactly `Handle Status Checks`
3. Authorize the pipeline to use the `AzureSDKEngKeyVault Secrets` service connection

---

### 4. GitHub Branch Protection Update *(one-time)*

- Remove `check-enforcer` from required status checks on `main`
- Add `Handle Status Checks` as the sole required status check

---

### 5. Retire check-enforcer *(cleanup)*

Once `Handle Status Checks` is validated in production, remove or disable the check-enforcer GitHub Actions workflow.

---

## Edge Cases / Risks

| Concern | Mitigation |
|---|---|
| Pipeline completion trigger uses default-branch YAML | Merge `handle-status-checks.yml` to `main` before relying on it |
| Self-identification: must match AzDO-reported check name exactly | Confirm the string after first test run; update jq filter if needed |
| GitHub API pagination (>100 checks) | Add page loop if needed; unlikely for this repo |
| Race condition: other checks haven't started yet when this fires | Treating `queued` as blocking handles this |
| Trigger fires for non-PR runs (scheduled, manual) | Add condition on `resources.pipeline.<alias>.triggerBuildReason == 'PullRequest'` |
