<#
.SYNOPSIS
    Detects the full blast radius of a change by tracing transitive YAML pipeline references
    and mapping them to Azure DevOps build definitions.

.DESCRIPTION
    This script:
    1. Searches GitHub (Microsoft/Azure orgs) for all files referencing the input string
    2. Performs a transitive closure upward through YAML pipeline references (template/extends chains)
    3. Maps root pipeline YAML files to Azure DevOps build definitions in azure-sdk/internal

    Rate-limited to stay under GitHub code search limits (10 req/min).

.PARAMETER SearchPhrase
    The string/pattern to search for (e.g., a file path, secret name, function reference).

.PARAMETER File
    Path to a file whose content will be used as the search input.

.PARAMETER Orgs
    GitHub organizations to search. Defaults to @("Microsoft", "Azure").

.PARAMETER MaxDepth
    Maximum depth for transitive closure traversal. Defaults to 5.

.PARAMETER RequestsPerMinute
    Rate limit for GitHub code search requests. Defaults to 8 (conservative under the 10/min cap).

.PARAMETER AdoProject
    Azure DevOps project URL. Defaults to "https://dev.azure.com/azure-sdk/internal".

.PARAMETER IncludeAdoLookup
    If set, queries ADO build definitions to map root YAML files. Requires ADO_TOKEN env var.

.EXAMPLE
    ./Search-Blast-Radius.ps1 -SearchPhrase "eng/common/pipelines/templates/steps/verify-links.yml"

.EXAMPLE
    ./Search-Blast-Radius.ps1 -SearchPhrase '$(azuresdk-github-pat)' -IncludeAdoLookup

.EXAMPLE
    ./Search-Blast-Radius.ps1 -File ./changed-files.txt -IncludeAdoLookup
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$SearchPhrase,

    [Parameter(Mandatory = $false)]
    [string]$File,

    [Parameter(Mandatory = $false)]
    [string[]]$Orgs = @("Microsoft", "Azure"),

    [Parameter(Mandatory = $false)]
    [int]$MaxDepth = 5,

    [Parameter(Mandatory = $false)]
    [int]$RequestsPerMinute = 8,

    [Parameter(Mandatory = $false)]
    [string]$AdoProject = "https://dev.azure.com/azure-sdk/internal",

    [Parameter(Mandatory = $false)]
    [switch]$IncludeAdoLookup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ============================================================================
# Input Resolution
# ============================================================================

function Resolve-SearchInput {
    if ($SearchPhrase -and $File) {
        throw "Specify either -SearchPhrase or -File, not both."
    }
    if (-not $SearchPhrase -and -not $File) {
        throw "Specify either -SearchPhrase or -File."
    }
    if ($File) {
        if (-not (Test-Path $File)) {
            throw "File not found: $File"
        }
        return (Get-Content $File -Raw).Trim()
    }
    return $SearchPhrase
}

# ============================================================================
# Rate Limiter
# ============================================================================

$script:RequestTimestamps = [System.Collections.Generic.List[datetime]]::new()

function Wait-RateLimit {
    $now = [datetime]::UtcNow
    $windowStart = $now.AddSeconds(-60)

    # Prune timestamps older than 60s
    $script:RequestTimestamps = [System.Collections.Generic.List[datetime]](
        $script:RequestTimestamps | Where-Object { $_ -gt $windowStart }
    )

    if ($script:RequestTimestamps.Count -ge $RequestsPerMinute) {
        $oldest = $script:RequestTimestamps[0]
        $waitSeconds = [math]::Ceiling(($oldest.AddSeconds(60) - $now).TotalSeconds)
        if ($waitSeconds -gt 0) {
            Write-Host "  [Rate Limit] Waiting ${waitSeconds}s before next request..." -ForegroundColor Yellow
            Start-Sleep -Seconds $waitSeconds
        }
    }

    $script:RequestTimestamps.Add([datetime]::UtcNow)
}

# ============================================================================
# GitHub Code Search
# ============================================================================

function Invoke-GitHubCodeSearch {
    param(
        [string]$Query,
        [string]$Extension,
        [int]$Limit = 100
    )

    Wait-RateLimit

    $searchArgs = @("search", "code", $Query, "--limit", $Limit, "--json", "path,repository,textMatches,url")

    foreach ($org in $Orgs) {
        $searchArgs += @("--owner", $org)
    }

    if ($Extension) {
        $searchArgs += @("--extension", $Extension)
    }

    Write-Host "  [Search] gh $($searchArgs -join ' ')" -ForegroundColor DarkGray

    $result = & gh @searchArgs 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "GitHub search failed: $result"
        return @()
    }

    try {
        $parsed = $result | ConvertFrom-Json
        return $parsed
    }
    catch {
        Write-Warning "Failed to parse search results: $_"
        return @()
    }
}

# ============================================================================
# Transitive Closure (BFS upward through YAML references)
# ============================================================================

function Get-TransitiveClosure {
    param(
        [string]$SearchTerm
    )

    # Each node is identified by "repo:path"
    $visited = [System.Collections.Generic.HashSet[string]]::new()
    # Queue contains file paths to search for in YAML files (level 1+)
    $queue = [System.Collections.Generic.Queue[hashtable]]::new()
    $graph = [System.Collections.Generic.List[hashtable]]::new()

    # ------------------------------------------------------------------
    # Phase 1: Search for the PHRASE itself. Any file type.
    # This finds the "leaf" files that directly contain the input.
    # ------------------------------------------------------------------
    Write-Host "`n[Phase 1] Searching for phrase: '$SearchTerm'" -ForegroundColor Cyan

    $initialResults = Invoke-GitHubCodeSearch -Query "`"$SearchTerm`"" -Limit 100

    if (-not $initialResults -or $initialResults.Count -eq 0) {
        Write-Host "  No results found." -ForegroundColor Yellow
        return @{ Graph = @(); Roots = @() }
    }

    Write-Host "  Found $($initialResults.Count) files containing the phrase." -ForegroundColor Green

    foreach ($result in $initialResults) {
        $nodeKey = "$($result.repository.nameWithOwner):$($result.path)"
        if ($visited.Add($nodeKey)) {
            $node = @{
                Repo         = $result.repository.nameWithOwner
                Path         = $result.path
                Url          = $result.url
                Depth        = 0
                ReferencedBy = [System.Collections.Generic.List[string]]::new()
                References   = $SearchTerm  # what this node contains/references
                IsYaml       = ([System.IO.Path]::GetExtension($result.path) -in @(".yml", ".yaml"))
            }
            $graph.Add($node)

            # Every discovered file gets queued for upward tracing
            # (we want to find what YAML references it)
            $queue.Enqueue($node)
        }
    }

    # ------------------------------------------------------------------
    # Phase 2: Climb the YAML reference chain.
    # For each file found, search for its PATH in YAML files.
    # If a YAML file references it, that YAML becomes the next file
    # to search for. Only YAML files continue the chain.
    # ------------------------------------------------------------------
    Write-Host "`n[Phase 2] Climbing YAML reference chain (max depth: $MaxDepth)..." -ForegroundColor Cyan

    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()

        if ($current.Depth -ge $MaxDepth) {
            Write-Host "  [Depth $($current.Depth)] Hit max depth, stopping traversal for: $($current.Path)" -ForegroundColor Yellow
            continue
        }

        # Build search term from the file's path.
        # Use the most distinctive trailing segments to balance precision vs recall.
        $pathToSearch = $current.Path
        $segments = $pathToSearch -split "/"
        if ($segments.Count -gt 3) {
            # Use last 3 segments: e.g. "templates/steps/verify-links.yml"
            $pathToSearch = ($segments[-3..-1] -join "/")
        }

        $nextDepth = $current.Depth + 1
        Write-Host "  [Depth $nextDepth] Finding YAML that references: $pathToSearch" -ForegroundColor DarkCyan

        # Search ONLY yml files for this path
        $references = Invoke-GitHubCodeSearch -Query "`"$pathToSearch`"" -Extension "yml" -Limit 100

        if (-not $references -or $references.Count -eq 0) {
            Write-Host "    No upstream YAML references found (this is a root)." -ForegroundColor DarkGray
            continue
        }

        Write-Host "    Found $($references.Count) referencing YAML files." -ForegroundColor Green

        foreach ($ref in $references) {
            $refKey = "$($ref.repository.nameWithOwner):$($ref.path)"

            # Skip self-references
            if ($refKey -eq "$($current.Repo):$($current.Path)") {
                continue
            }

            # Record that current node is referenced by this YAML file
            $current.ReferencedBy.Add($refKey)

            # If we haven't seen this YAML file yet, add it to the graph and queue
            if ($visited.Add($refKey)) {
                $refNode = @{
                    Repo         = $ref.repository.nameWithOwner
                    Path         = $ref.path
                    Url          = $ref.url
                    Depth        = $nextDepth
                    ReferencedBy = [System.Collections.Generic.List[string]]::new()
                    References   = $current.Path
                    IsYaml       = $true  # we filtered to yml extension
                }
                $graph.Add($refNode)

                # YAML files continue the chain - search for what references THEM
                $queue.Enqueue($refNode)
            }
            else {
                # Node already visited, but still record the edge
                $existingNode = $graph | Where-Object {
                    "$($_.Repo):$($_.Path)" -eq $refKey
                } | Select-Object -First 1
                # (edge already tracked via current.ReferencedBy)
            }
        }
    }

    # ------------------------------------------------------------------
    # Identify root YAML files: those that have NO upstream references
    # (nothing in the graph references them). These are pipeline entry points.
    # ------------------------------------------------------------------
    $roots = $graph | Where-Object {
        $_.IsYaml -and $_.ReferencedBy.Count -eq 0
    }

    Write-Host "`n  Graph complete: $($graph.Count) nodes, $($roots.Count) root pipelines." -ForegroundColor Green

    return @{
        Graph = $graph
        Roots = @($roots)
    }
}

# ============================================================================
# Azure DevOps Build Definition Lookup
# ============================================================================

function Get-AdoBuildDefinitions {
    param(
        [hashtable[]]$RootYamlFiles
    )

    $adoToken = $env:ADO_TOKEN
    if (-not $adoToken) {
        Write-Warning "ADO_TOKEN environment variable not set. Skipping ADO build definition lookup."
        return @()
    }

    Write-Host "`n[Phase 3] Querying ADO build definitions..." -ForegroundColor Cyan

    $headers = @{
        Authorization  = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(":$adoToken"))
        "Content-Type" = "application/json"
    }

    # Get all build definitions (paginated)
    $allDefinitions = [System.Collections.Generic.List[object]]::new()
    $continuationToken = $null

    do {
        $url = "$AdoProject/_apis/build/definitions?api-version=7.1&`$top=200"
        if ($continuationToken) {
            $url += "&continuationToken=$continuationToken"
        }

        try {
            $response = Invoke-WebRequest -Uri $url -Headers $headers -Method Get
            $body = $response.Content | ConvertFrom-Json
            $allDefinitions.AddRange($body.value)

            # ADO returns continuation token in headers
            $continuationToken = $response.Headers["x-ms-continuationtoken"]
        }
        catch {
            Write-Warning "ADO API request failed: $_"
            $continuationToken = $null
        }
    } while ($continuationToken)

    Write-Host "  Retrieved $($allDefinitions.Count) build definitions." -ForegroundColor Green

    # Match root YAML files to build definitions
    $matches = [System.Collections.Generic.List[hashtable]]::new()

    foreach ($root in $RootYamlFiles) {
        foreach ($def in $allDefinitions) {
            $yamlFilename = $null
            if ($def.process -and $def.process.yamlFilename) {
                $yamlFilename = $def.process.yamlFilename
            }

            $repoName = $null
            if ($def.repository -and $def.repository.name) {
                $repoName = $def.repository.name
            }

            if (-not $yamlFilename) { continue }

            # Match by YAML filename (normalize path separators)
            $normalizedRoot = $root.Path -replace "\\", "/"
            $normalizedYaml = $yamlFilename -replace "\\", "/"

            if ($normalizedYaml -eq $normalizedRoot -or $normalizedYaml.EndsWith($normalizedRoot)) {
                # Check repo match if available
                $repoMatch = (-not $repoName) -or ($root.Repo -like "*/$repoName") -or ($root.Repo -eq $repoName)

                if ($repoMatch) {
                    $matches.Add(@{
                        Definition   = @{
                            Id   = $def.id
                            Name = $def.name
                            Url  = "$AdoProject/_build?definitionId=$($def.id)"
                            Yaml = $yamlFilename
                            Repo = $repoName
                        }
                        RootYaml     = $root
                    })
                }
            }
        }
    }

    return $matches
}

# ============================================================================
# Output Formatting
# ============================================================================

function Write-BlastRadiusReport {
    param(
        [hashtable]$Closure,
        [array]$AdoMatches,
        [string]$SearchTerm
    )

    Write-Host "`n" -NoNewline
    Write-Host ("=" * 80) -ForegroundColor White
    Write-Host " BLAST RADIUS REPORT" -ForegroundColor White
    Write-Host ("=" * 80) -ForegroundColor White
    Write-Host "`n  Search Term: $SearchTerm" -ForegroundColor White

    # Summary
    $graph = $Closure.Graph
    $roots = $Closure.Roots

    Write-Host "`n  Total files in reference graph: $($graph.Count)" -ForegroundColor White
    Write-Host "  Root pipeline YAML files:       $($roots.Count)" -ForegroundColor White

    # Depth breakdown
    $depthGroups = $graph | Group-Object -Property Depth | Sort-Object Name
    Write-Host "`n  Depth breakdown:" -ForegroundColor White
    foreach ($group in $depthGroups) {
        Write-Host "    Depth $($group.Name): $($group.Count) files" -ForegroundColor Gray
    }

    # Repo breakdown
    $repoGroups = $graph | Group-Object -Property Repo | Sort-Object Count -Descending
    Write-Host "`n  Repository breakdown:" -ForegroundColor White
    foreach ($group in $repoGroups | Select-Object -First 20) {
        Write-Host "    $($group.Name): $($group.Count) files" -ForegroundColor Gray
    }

    # Root YAML files
    if ($roots.Count -gt 0) {
        Write-Host "`n  Root pipeline files (entry points):" -ForegroundColor White
        foreach ($root in $roots | Sort-Object { $_.Repo }) {
            Write-Host "    - $($root.Repo)/$($root.Path)" -ForegroundColor Cyan
        }
    }

    # ADO Build Definitions
    if ($AdoMatches -and $AdoMatches.Count -gt 0) {
        Write-Host "`n  ADO Build Definitions affected:" -ForegroundColor White
        foreach ($match in $AdoMatches | Sort-Object { $_.Definition.Name }) {
            Write-Host "    - [$($match.Definition.Id)] $($match.Definition.Name)" -ForegroundColor Magenta
            Write-Host "      YAML: $($match.Definition.Yaml)" -ForegroundColor DarkGray
            Write-Host "      URL:  $($match.Definition.Url)" -ForegroundColor DarkGray
        }
    }

    Write-Host "`n$("=" * 80)" -ForegroundColor White

    # Return structured output for piping
    return @{
        SearchTerm  = $SearchTerm
        Graph       = $graph
        Roots       = $roots
        AdoMatches  = $AdoMatches
        Summary     = @{
            TotalFiles     = $graph.Count
            RootPipelines  = $roots.Count
            AdoDefinitions = if ($AdoMatches) { $AdoMatches.Count } else { 0 }
            Repos          = ($repoGroups | ForEach-Object { @{ Name = $_.Name; Count = $_.Count } })
        }
    }
}

# ============================================================================
# Main Execution
# ============================================================================

$searchTerm = Resolve-SearchInput

Write-Host "Blast Radius Detection" -ForegroundColor White
Write-Host "======================" -ForegroundColor White
Write-Host "  Target: $searchTerm"
Write-Host "  Orgs:   $($Orgs -join ', ')"
Write-Host "  Rate:   $RequestsPerMinute req/min"
Write-Host "  Depth:  $MaxDepth"

# Run transitive closure
$closure = Get-TransitiveClosure -SearchTerm $searchTerm

# ADO lookup if requested
$adoMatches = @()
if ($IncludeAdoLookup -and $closure.Roots.Count -gt 0) {
    $adoMatches = Get-AdoBuildDefinitions -RootYamlFiles $closure.Roots
}

# Report
$report = Write-BlastRadiusReport -Closure $closure -AdoMatches $adoMatches -SearchTerm $searchTerm

# Output structured JSON to pipeline
$report | ConvertTo-Json -Depth 10
