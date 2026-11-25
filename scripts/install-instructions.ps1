# Copies the shipped instruction defaults (instructions/skills) into the user-editable store that
# TokenSaver reads. Copy-only-when-missing: an existing skill folder is never overwritten, so the
# user's edits survive re-running this script. Pass -Force to replace existing folders with defaults.
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$source = Join-Path $PSScriptRoot '..\instructions\skills' | Resolve-Path
$destRoot = if ($env:TOKENSAVER_INSTRUCTIONS_DIR) {
    $env:TOKENSAVER_INSTRUCTIONS_DIR
} else {
    Join-Path $env:USERPROFILE '.tokensaver\instructions\skills'
}

New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

$copied = 0
$kept = 0
foreach ($skill in Get-ChildItem -Path $source -Directory) {
    $target = Join-Path $destRoot $skill.Name
    if ((Test-Path $target) -and -not $Force) {
        $kept++
        Write-Host "kept     $($skill.Name) (exists; edits preserved)"
        continue
    }

    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
    Copy-Item -Recurse -Path $skill.FullName -Destination $target
    $copied++
    Write-Host "copied   $($skill.Name)"
}

Write-Host ""
Write-Host "Store: $destRoot"
Write-Host "Copied: $copied, kept: $kept"
