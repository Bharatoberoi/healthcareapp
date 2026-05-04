<#
scripts/start_all.ps1

Starts the whole application (Windows PowerShell).
Run from the repository root:
  .\scripts\start_all.ps1
#>

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir '..')
$projectRoot = $projectRoot.Path

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error "Python executable not found at $python. Activate the venv or adjust the path in this script."
    exit 1
}

# ensure logs directory
$logs = Join-Path $projectRoot 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }

function Start-App($name, [string[]]$appArgs) {
    Write-Host "Starting: $name -> $($appArgs -join ' ')" -ForegroundColor Cyan
    $proc = Start-Process -FilePath $python -ArgumentList $appArgs -PassThru
    Start-Sleep -Milliseconds 300
    return @{ name = $name; pid = $proc.Id }
}

# start MCP servers + API + simple file server for frontend
$pids = @()
$pids += Start-App 'provider_lookup' @('app/mcp/provider_lookup_mcp.py')
$pids += Start-App 'cost_estimator' @('app/mcp/cost_estimator_mcp.py')
$pids += Start-App 'api' @('run_app.py')
$pids += Start-App 'frontend' @('-m', 'http.server', '8080', '--directory', $projectRoot)

# save PIDs for stop script
$pidsFile = Join-Path $scriptDir 'pids.json'
$pids | ConvertTo-Json | Set-Content -Path $pidsFile -Encoding UTF8

Write-Host "\nStarted processes:" -ForegroundColor Green
$pids | ForEach-Object { Write-Host " - $($_.name) (PID $($_.pid))" }

# give servers a moment to start then open browser
Start-Sleep -Seconds 1
Start-Process "http://localhost:8080/frontend.html"
Start-Process "http://localhost:8000/docs"
Write-Host "\nFrontend: http://localhost:8080/frontend.html"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host "Use .\scripts\stop_all.ps1 to stop the processes." -ForegroundColor Yellow