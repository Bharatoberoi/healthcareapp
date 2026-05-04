# Deploy this repo to Amazon Lightsail Container Service (fixed low monthly price vs Fargate/App Runner complexity).
#
# Prereqs:
#   1) AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
#   2) Docker Desktop running
#   3) Authenticate once (pick ONE):
#        aws configure
#      OR
#        aws sso login --profile your-profile
#        $env:AWS_PROFILE = "your-profile"
#
# Secrets: set OPENAI_API_KEY in your shell before running, or edit the script.
#
# Usage (from repo root):
#   cd "path\to\code_3 - Copy"
#   $env:OPENAI_API_KEY = "sk-..."
#   .\scripts\deploy_aws_lightsail.ps1
#
# Optional: -ServiceName, -Region, -Power (nano|micro|small; default micro for FAISS+uvicorn)

[CmdletBinding()]
param(
    [string] $ServiceName = "medical-cost-api",
    [string] $Region = "us-east-1",
    [ValidateSet("nano", "micro", "small", "medium", "large", "xlarge")]
    [string] $Power = "micro",
    [int] $Scale = 1,
    [string] $ImageTag = "medical-cost-api:lightsail"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

if (-not (Test-Path (Join-Path $Root "Dockerfile"))) {
    throw "Run from repo root context; Dockerfile not found under $Root"
}

Write-Host "Checking AWS identity..." -ForegroundColor Cyan
$ident = aws sts get-caller-identity 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $ident
    throw "AWS not authenticated. Run: aws configure   (Access key, Secret, default region $Region)"
}

if (-not $env:OPENAI_API_KEY) {
    throw "Set OPENAI_API_KEY in the environment before deploying (example: `$env:OPENAI_API_KEY = 'sk-...')"
}

Write-Host "Building image $ImageTag ..." -ForegroundColor Cyan
Push-Location $Root
try {
    docker build -t $ImageTag .
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
} finally {
    Pop-Location
}

$servicesJson = aws lightsail get-container-services --region $Region 2>&1
if ($LASTEXITCODE -ne 0) { throw "lightsail get-container-services failed: $servicesJson" }

$exists = $false
try {
    $svcList = $servicesJson | ConvertFrom-Json
    $exists = $svcList.containerServices | Where-Object { $_.serviceName -eq $ServiceName }
} catch { }

if (-not $exists) {
    Write-Host "Creating Lightsail service $ServiceName ($Power, scale $Scale)..." -ForegroundColor Cyan
    aws lightsail create-container-service `
        --service-name $ServiceName `
        --power $Power `
        --scale $Scale `
        --region $Region
    if ($LASTEXITCODE -ne 0) { throw "create-container-service failed" }
}

Write-Host "Waiting for service state RUNNING (can take a few minutes)..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(15)
do {
    $svc = aws lightsail get-container-services --service-name $ServiceName --region $Region | ConvertFrom-Json
    $state = $svc.containerServices[0].state
    Write-Host "  state=$state"
    if ($state -eq "RUNNING") { break }
    if ($state -eq "FAILED" -or $state -eq "PENDING_DELETE") { throw "Service entered bad state: $state" }
    if ((Get-Date) -gt $deadline) { throw "Timeout waiting for RUNNING" }
    Start-Sleep -Seconds 10
} while ($true)

Write-Host "Pushing image to Lightsail..." -ForegroundColor Cyan
$pushOut = aws lightsail push-container-image `
    --region $Region `
    --service-name $ServiceName `
    --label app `
    --image $ImageTag 2>&1
if ($LASTEXITCODE -ne 0) { throw "push-container-image failed: $pushOut" }

# Extract image reference like :medical-cost-api.app.7
$imageRef = ($pushOut | Select-String -Pattern 'Refer to this image as "(:[^"]+)"').Matches.Groups[1].Value
if (-not $imageRef) {
    $imageRef = ($pushOut | Select-String -Pattern ":[a-zA-Z0-9._-]+\.[a-zA-Z0-9._-]+\.\d+").Matches[0].Value
}
if (-not $imageRef) {
    Write-Host $pushOut
    throw "Could not parse image reference from push output. Use the 'Refer to this image as' value manually in deploy JSON."
}

Write-Host "Using image ref: $imageRef" -ForegroundColor Green

$deployObj = [ordered]@{
    serviceName    = $ServiceName
    containers     = @{
        app = @{
            image       = $imageRef
            ports       = @{ "8080" = "HTTP" }
            environment = @{
                PORT            = "8080"
                UVICORN_WORKERS = "1"
                PRELOAD_FAISS   = "true"
                LOG_LEVEL       = "INFO"
                ENVIRONMENT     = "production"
                OPENAI_API_KEY  = $env:OPENAI_API_KEY
            }
        }
    }
    publicEndpoint = @{
        containerName = "app"
        containerPort = 8080
        healthCheck   = @{
            path               = "/health"
            intervalSeconds    = 15
            timeoutSeconds     = 5
            healthyThreshold   = 2
            unhealthyThreshold = 3
        }
    }
}
$deploy = $deployObj | ConvertTo-Json -Depth 10

$tmp = [System.IO.Path]::GetTempFileName() + ".json"
# BOM-free UTF8 for AWS CLI on Windows
[System.IO.File]::WriteAllText($tmp, $deploy)

Write-Host "Creating deployment..." -ForegroundColor Cyan
$fileUrl = "file:///" + ($tmp -replace "\\", "/")
aws lightsail create-container-service-deployment `
    --cli-input-json $fileUrl `
    --region $Region
Remove-Item $tmp -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) { throw "create-container-service-deployment failed" }

Write-Host ""
Write-Host "Deployment submitted. URL (after ACTIVE):" -ForegroundColor Green
$url = (aws lightsail get-container-services --service-name $ServiceName --region $Region | ConvertFrom-Json).containerServices[0].url
Write-Host "  $url"
Write-Host "Track: AWS Console -> Lightsail -> Containers -> $ServiceName"
