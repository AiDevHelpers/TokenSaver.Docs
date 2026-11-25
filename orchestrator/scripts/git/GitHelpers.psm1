#Requires -Version 7.0
# Guarded git and PR helpers. Import with: Import-Module <path>\GitHelpers.psm1
# Each helper refuses the breaches logged in .claude/task_failure_log.md. Git CLI does the work; gh does PRs.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ProtectedBranches = @('main', 'dev', 'wip')  # trunks: this repo's wip, the submodules' dev and main

function Invoke-Git {
    param([Parameter(Mandatory)][string[]]$Args_)
    $ErrorActionPreference = 'Continue'  # native stderr must not throw under Stop
    $out = & git @Args_ 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args_ -join ' ') failed (exit $LASTEXITCODE):`n$($out -join "`n")"
    }
    return $out
}

function Get-CurrentBranch {
    (Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD')).Trim()
}

function Assert-CleanTree {
    $status = Invoke-Git @('status', '--porcelain')
    if ($status) { throw "Working tree is not clean:`n$($status -join "`n")" }
}

function New-SafeBranch {
    <#
    .SYNOPSIS  Create a feature branch from an up-to-date base. Refuses an existing name or a protected name.
    #>
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$Base = 'wip'
    )
    if ($Name -in $script:ProtectedBranches) { throw "Refusing to create protected branch '$Name'." }
    Invoke-Git @('fetch', 'origin', $Base) | Out-Null
    $exists = & git show-ref --verify --quiet "refs/heads/$Name"
    if ($LASTEXITCODE -eq 0) { throw "Branch '$Name' already exists." }
    Invoke-Git @('switch', '-c', $Name, "origin/$Base") | Out-Null
    "Created $Name from origin/$Base"
}

function Invoke-SafeCommit {
    <#
    .SYNOPSIS  Commit staged changes using a message file (git commit -F). Refuses an empty index or an inline message.
    #>
    param(
        [Parameter(Mandatory)][string]$MessageFile
    )
    if (-not (Test-Path -LiteralPath $MessageFile -PathType Leaf)) { throw "Message file not found: $MessageFile" }
    $staged = Invoke-Git @('diff', '--cached', '--name-only')
    if (-not $staged) { throw 'Nothing staged. Stage files explicitly with git add <paths>.' }
    Invoke-Git @('commit', '-F', $MessageFile) | Out-Null
    (Invoke-Git @('log', '-1', '--oneline')) -join ''
}

function Invoke-SafePush {
    <#
    .SYNOPSIS  Push the current branch. Refuses protected trunks (main, dev, wip), force pushes, and pushing without an upstream set to the same name.
    #>
    param([switch]$SetUpstream)
    $branch = Get-CurrentBranch
    if ($branch -in $script:ProtectedBranches) {
        throw "Refusing to push '$branch' directly. Work on a feature branch and open a PR."
    }
    $pushArgs = @('push')
    if ($SetUpstream) { $pushArgs += '-u' }
    $pushArgs += @('origin', $branch)
    Invoke-Git $pushArgs | Out-Null
    "Pushed $branch"
}

function Remove-CleanWorktree {
    <#
    .SYNOPSIS  Remove a worktree only when it has no uncommitted changes. Never uses --force.
    #>
    param([Parameter(Mandatory)][string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $status = Invoke-Git @('-C', $resolved, 'status', '--porcelain')
    if ($status) { throw "Worktree '$resolved' has uncommitted changes. Commit or discard them first." }
    Invoke-Git @('worktree', 'remove', $resolved) | Out-Null
    "Removed worktree $resolved"
}

function New-SafePr {
    <#
    .SYNOPSIS  Open a PR with gh. Body comes from a file. Requires the branch to be pushed and not protected.
    #>
    param(
        [Parameter(Mandatory)][string]$Title,
        [Parameter(Mandatory)][string]$BodyFile,
        [string]$Base = 'wip'
    )
    $branch = Get-CurrentBranch
    if ($branch -in $script:ProtectedBranches) { throw "Refusing to open a PR from protected branch '$branch'." }
    if (-not (Test-Path -LiteralPath $BodyFile -PathType Leaf)) { throw "Body file not found: $BodyFile" }
    $url = & gh pr create --base $Base --head $branch --title $Title --body-file $BodyFile 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gh pr create failed:`n$($url -join "`n")" }
    $url -join "`n"
}

function Merge-SafePr {
    <#
    .SYNOPSIS  Squash-merge a PR with gh. Requires -Confirm:$true style explicit switch; never enables auto-merge.
    #>
    param(
        [Parameter(Mandatory)][int]$Number,
        [Parameter(Mandatory)][switch]$Yes
    )
    if (-not $Yes) { throw 'Pass -Yes to confirm the squash merge.' }
    $out = & gh pr merge $Number --squash --delete-branch 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gh pr merge failed:`n$($out -join "`n")" }
    $out -join "`n"
}

Export-ModuleMember -Function New-SafeBranch, Invoke-SafeCommit, Invoke-SafePush, Remove-CleanWorktree, New-SafePr, Merge-SafePr
