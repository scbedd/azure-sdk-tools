# Plan: Replace `check-enforcer` with "All Checks Pass" ADO Pipeline Template

## Problem

The repo currently uses a `check-enforcer` GitHub Action (`.github/workflows/event.yml` + `azure/azure-sdk-actions@main`) that watches all check suites and posts an aggregate status. It's being retired. We need a replacement that:

- Runs as a **final step/job** in each Azure DevOps pipeline
- Evaluates all checks on the PR's head commit via the GitHub API
- Posts an **"All Checks Pass"** commit status: `pending`, `failure`, or `success`
- Uses `eng/common/pipelines/templates/steps/login-to-github.yml` for GitHub auth (`GH_TOKEN`)

## Approach

Create a new ADO pipeline **step template** + backing **PowerShell script**. Each pipeline that can trigger on a PR adds this template as a final step (with `condition: always()` so it runs even on failure). The script queries GitHub for all check runs and commit statuses on the head commit, excludes itself, and posts the aggregate result.

## Deliverables

### 1. PowerShell Script: `eng/common/scripts/post-all-checks-status.ps1`

Core logic:
1. Accept parameters: `$CommitSha`, `$RepoOwner`, `$RepoName`
2. Query `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` (paginated) to get all check runs (ADO pipelines via GitHub App, GitHub Actions)
3. Query `GET /repos/{owner}/{repo}/commits/{sha}/status` to get all commit statuses
4. Exclude checks named "All Checks Pass" and "check-enforcer" (migration period) from evaluation
5. Determine aggregate state:
   - If ANY check is `failure`, `cancelled`, `timed_out`, or `action_required` → post **failure**
   - If ANY check is `queued`, `in_progress`, or `pending` → post **pending**
   - If ALL checks are `success`/`completed` with `success`/`neutral`/`skipped` conclusions → post **success**
6. Post via `POST /repos/{owner}/{repo}/statuses/{sha}` with context `"All Checks Pass"`

### 2. ADO Step Template: `eng/common/pipelines/templates/steps/post-all-checks-status.yml`

```yaml
parameters:
- name: RepoOwner
  type: string
  default: Azure
- name: RepoName
  type: string
  default: azure-sdk-tools

steps:
- template: /eng/common/pipelines/templates/steps/login-to-github.yml
  parameters:
    TokenOwners:
      - ${{ parameters.RepoOwner }}
- pwsh: |
    eng/common/scripts/post-all-checks-status.ps1 \
      -CommitSha "$(Build.SourceVersion)" \
      -RepoOwner "${{ parameters.RepoOwner }}" \
      -RepoName "${{ parameters.RepoName }}"
  displayName: "Post 'All Checks Pass' Status"
  condition: always()
  env:
    GH_TOKEN: $(GH_TOKEN)
```

### 3. Integration into Existing Pipelines

Add the template call as a final step in each pipeline that can trigger on PRs. Example with `tools/test-proxy/ci.yml`:

```yaml
extends:
  template: /eng/pipelines/templates/stages/archetype-sdk-tool-dotnet.yml
  parameters:
    ToolDirectory: tools/test-proxy
    # ... existing params ...
    PostSteps:
      - template: /eng/common/pipelines/templates/steps/post-all-checks-status.yml
```

> Note: The exact injection point depends on whether the archetype template supports a `PostSteps` or `FinalSteps` parameter, or if we need to add a new final job/stage. We'll determine this during implementation.

### 4. Migration Steps (out of scope for code, but noted)

- Add `"All Checks Pass"` as a required check in branch protection for `main`
- Remove `"check-enforcer"` from required checks
- Delete or disable `.github/workflows/event.yml`

## Todos

1. **create-ps-script** — Create `eng/common/scripts/post-all-checks-status.ps1` with the check aggregation logic
2. **create-step-template** — Create `eng/common/pipelines/templates/steps/post-all-checks-status.yml` ADO step template
3. **integrate-test-proxy** — Add the template call to `tools/test-proxy/ci.yml` as a proof-of-concept integration
4. **cleanup-check-enforcer** — Remove or disable `.github/workflows/event.yml` (do after migration)

## Key Design Decisions

- **Commit status** (not check run): We post a commit status via `POST /repos/{owner}/{repo}/statuses/{sha}` because it's simpler and doesn't require a GitHub App check-run integration. Context name = `"All Checks Pass"`.
- **Exclude self + check-enforcer**: The script must filter these out to avoid circular evaluation and to support the migration period.
- **`condition: always()`**: The template step runs even when the pipeline fails, ensuring a "failure" status is posted.
- **Idempotent**: Multiple pipelines finishing around the same time may all post — the last one to post wins, which is correct since the last one has the most complete view of all checks.
