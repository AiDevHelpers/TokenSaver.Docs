#Requires -Version 7
<#
.SYNOPSIS
  Rebuilds and updates all TokenSaver components: MCP service and VS extension.

.DESCRIPTION
  Performs a full rebuild and reinstall cycle:
  1. Stops the TokenSaver Windows Service (if running)
  2. Rebuilds and replaces the MCP server binary
  3. Rebuilds the VS extension VSIX
  4. Uninstalls the old VS extension
  5. Installs the new VS extension
  6. Restarts the TokenSaver Windows Service

  Requires Administrator privileges for service operations.
  Use for production deployments or comprehensive development updates.
#>
param(
  [string]$Configuration = "Release",
  [switch]$NoService      # skip Windows Service updates (dev-only MCP)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot | Split-Path -Parent

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  TokenSaver - Full Component Update                       ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# ── Update MCP Service ───────────────────────────────────────────────────────
if (-not $NoService) {
  Write-Host ""
  Write-Host "==> Step 1/3: Updating MCP Server Service" -ForegroundColor Cyan
  & (Join-Path $RepoRoot "scripts\rebuild-and-replace-mcp.ps1") -Configuration $Configuration
  if ($LASTEXITCODE -ne 0) {
    throw "MCP server rebuild failed"
  }
} else {
  Write-Host ""
  Write-Host "==> Step 1/3: Skipping MCP Service (dev mode)" -ForegroundColor Yellow
}

# ── Update VS Extension ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "==> Step 2/3: Updating VS Extension" -ForegroundColor Cyan
& (Join-Path $RepoRoot "scripts\update-vs-extension.ps1") -Configuration $Configuration
if ($LASTEXITCODE -ne 0) {
  throw "VS Extension update failed"
}

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✓ All components updated successfully                    ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Reload Visual Studio to activate the new extension"
Write-Host "  2. Verify TokenSaver.MCP service is running (Services.msc)"
Write-Host "  3. Check extension health via Tools → TokenSaver → Health Check"
Write-Host ""
