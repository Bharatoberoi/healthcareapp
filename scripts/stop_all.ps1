<#
Scripts/stop_all.ps1
Stops processes started by start_all.ps1. Safe — tries to use recorded PIDs first.
Run from repository root: .\scripts\stop_all.ps1
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidsFile = Join-Path $scriptDir 'pids.json'

if (Test-Path $pidsFile) {
    try {
        $pids = Get-Content $pidsFile | ConvertFrom-Json
        foreach ($p in $pids) {
            if ($p.pid) {
                try { Stop-Process -Id $p.pid -Force -ErrorAction SilentlyContinue; Write-Host "Stopped $($p.name) (PID $($p.pid))" -ForegroundColor Green } catch {}
            }
        }
        Remove-Item $pidsFile -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped recorded processes." -ForegroundColor Green
        exit 0
    } catch {
        Write-Warning "Could not read pids.json — will attempt a safe cleanup by commandline match."
    }
}

# Fallback: try to find processes by command line
$names = @('provider_lookup_mcp.py','cost_estimator_mcp.py','run_app.py','http.server')
$procs = Get-CimInstance Win32_Process | Where-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return $false }
    foreach ($n in $names) { if ($cmd -match [regex]::Escape($n)) { return $true } }
    return $false
}

if ($procs) {
    foreach ($proc in $procs) {
        try { Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host "Stopped PID $($proc.ProcessId)" -ForegroundColor Green } catch {}
    }
    Write-Host "Stopped matching processes." -ForegroundColor Green
} else {
    Write-Host "No matching processes found." -ForegroundColor Yellow
}

Write-Host "If anything remains, check Task Manager or restart your shell." -ForegroundColor Yellow