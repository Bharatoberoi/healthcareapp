<#
Scripts/cleanup_workspace.ps1
Cleans up safe, reversible artifacts (pycache, .pyc). By default DOES NOT remove tests.
Usage:
  .\scripts\cleanup_workspace.ps1           # remove caches & .pyc
  .\scripts\cleanup_workspace.ps1 -RemoveTests  # also remove test_*.py files
#>

param(
    [switch]$RemoveTests
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir '..')
$projectRoot = $projectRoot.Path

Write-Host "Cleaning workspace (root=$projectRoot)" -ForegroundColor Cyan

# remove __pycache__ directories
Get-ChildItem -Path $projectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Removed: $($_.FullName)"
    } catch { Write-Warning "Failed to remove $($_.FullName)" }
}

# remove .pyc/.pyo
Get-ChildItem -Path $projectRoot -Recurse -Include *.pyc,*.pyo -File -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue; Write-Host "Removed: $($_.FullName)" } catch { }
}

if ($RemoveTests) {
    Write-Host "Removing test files (test_*.py, test*.py) -- confirming.." -ForegroundColor Yellow
    Get-ChildItem -Path $projectRoot -Recurse -Include test_*.py, test*.py -File -ErrorAction SilentlyContinue | ForEach-Object {
        try { Remove-Item -Path $_.FullName -Force; Write-Host "Removed: $($_.FullName)" } catch { Write-Warning "Failed to remove: $($_.FullName)" }
    }
}

Write-Host "Cleanup finished." -ForegroundColor Green