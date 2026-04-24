[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$CommitSha,

  [Parameter(Mandatory = $true)]
  [string]$RepoOwner,

  [Parameter(Mandatory = $true)]
  [string]$RepoName,

  [string]$StatusContext = "All Checks Pass",

  [string[]]$ExcludeContexts = @("check-enforcer")
)

Set-StrictMode -Version 3
$ErrorActionPreference = 'Stop'

# Contexts to always exclude from evaluation (self + explicit exclusions)
$allExclusions = @($StatusContext) + $ExcludeContexts

Write-Host "Evaluating checks for $RepoOwner/$RepoName @ $CommitSha"
Write-Host "Excluded contexts: $($allExclusions -join ', ')"

# --- Fetch all check runs (paginated) ---
Write-Host "`nFetching check runs..."
$checkRunsJson = gh api --paginate "/repos/$RepoOwner/$RepoName/commits/$CommitSha/check-runs" `
  --jq '.check_runs[] | {name, status, conclusion}' 2>&1

if ($LASTEXITCODE) {
  Write-Error "Failed to fetch check runs: $checkRunsJson"
  exit 1
}

$checkRuns = @()
if ($checkRunsJson) {
  $checkRuns = $checkRunsJson | ConvertFrom-Json
  # Normalize to array if single result
  if ($checkRuns -isnot [array]) {
    $checkRuns = @($checkRuns)
  }
}

# Filter out excluded contexts
$checkRuns = @($checkRuns | Where-Object { $_.name -notin $allExclusions })
Write-Host "Found $($checkRuns.Count) check run(s) after filtering"

# --- Fetch combined commit status ---
Write-Host "`nFetching commit statuses..."
$statusJson = gh api "/repos/$RepoOwner/$RepoName/commits/$CommitSha/status" 2>&1

if ($LASTEXITCODE) {
  Write-Error "Failed to fetch commit statuses: $statusJson"
  exit 1
}

$commitStatuses = @()
if ($statusJson) {
  $statusResponse = $statusJson | ConvertFrom-Json
  $commitStatuses = @($statusResponse.statuses | Where-Object { $_.context -notin $allExclusions })
}
Write-Host "Found $($commitStatuses.Count) commit status(es) after filtering"

# --- Evaluate aggregate state ---
$hasPending = $false
$hasFailure = $false
$failureDetails = @()

# Evaluate check runs
foreach ($run in $checkRuns) {
  Write-Host "  Check run: '$($run.name)' status=$($run.status) conclusion=$($run.conclusion)"

  if ($run.status -ne "completed") {
    $hasPending = $true
    continue
  }

  switch ($run.conclusion) {
    { $_ -in @("failure", "cancelled", "timed_out", "action_required") } {
      $hasFailure = $true
      $failureDetails += "'$($run.name)' ($($run.conclusion))"
    }
    # success, neutral, skipped are all OK
  }
}

# Evaluate commit statuses
foreach ($status in $commitStatuses) {
  Write-Host "  Commit status: '$($status.context)' state=$($status.state)"

  switch ($status.state) {
    "pending" { $hasPending = $true }
    { $_ -in @("error", "failure") } {
      $hasFailure = $true
      $failureDetails += "'$($status.context)' ($($status.state))"
    }
    # success is OK
  }
}

# --- Determine what to post ---
if ($hasFailure) {
  $state = "failure"
  $description = "Failed: $($failureDetails -join ', ')"
}
elseif ($hasPending) {
  $state = "pending"
  $description = "Waiting for checks to complete"
}
else {
  $totalChecks = $checkRuns.Count + $commitStatuses.Count
  if ($totalChecks -eq 0) {
    $state = "success"
    $description = "No checks to evaluate"
  }
  else {
    $state = "success"
    $description = "All $totalChecks check(s) passed"
  }
}

# Truncate description to 140 chars (GitHub API limit)
if ($description.Length -gt 140) {
  $description = $description.Substring(0, 137) + "..."
}

Write-Host "`nPosting status: $state - $description"

# --- Post commit status ---
$body = @{
  state       = $state
  description = $description
  context     = $StatusContext
} | ConvertTo-Json -Compress

$result = $body | gh api -X POST "/repos/$RepoOwner/$RepoName/statuses/$CommitSha" `
  -H "Accept: application/vnd.github+json" --input - 2>&1

if ($LASTEXITCODE) {
  Write-Error "Failed to post status: $result"
  exit 1
}

Write-Host "Successfully posted '$StatusContext' = $state"
