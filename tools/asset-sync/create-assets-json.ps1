<#
.SYNOPSIS
Creates an assets.json within the current working directory.

.DESCRIPTION
Leads the user on a guided prompt that gets them through the first transition to remote recordings.

#>
Function Collect-python-files($startDirectory){
   Get-ChildItem -Path $startDirectory -R -Include *.json
}

$template = [PSCustomObject]@{
   AssetsRepo = "Azure/azure-sdk-assets"
   AssetsRepoPrefixPath = ""
   AssetsRepoBranch = ""
   SHA = ""
}

$targetDirectory = Get-Location
$template2 = $template.psobject.copy()
$result = Read-Host -Prompt "What service are you creating this assets.json for? (Please enter acceptable git branch name)"

$testDirectories = @()


$results = Collect-python-files -startDirectory $targetDirectory

Write-Host $results

Write-Host "Found test files located in $($testDirectories)"

