<#
.SYNOPSIS
  Deploy Medical Cost API to Google Cloud Run (recommended vs GKE for typical cost + latency).

.DESCRIPTION
  - Cloud Run: no GKE control-plane / node-pool minimum; pay per use; scale to zero optional.
  - Low lag: use -MinInstances 1 to avoid cold starts (small steady cost).
  - OpenAI key: store in Secret Manager (recommended) or pass -OpenAiApiKey for a quick test deploy.

  Prerequisites: gcloud auth login, gcloud config set project YOUR_ID, Docker optional (--source builds in cloud).

  First deploy with --set-secrets: grant the Cloud Run service account (often PROJECT_NUMBER-compute@developer.gserviceaccount.com)
  roles/secretmanager.secretAccessor on each secret. Optional: Cloud SQL only if you use Postgres (this app defaults to FAISS on disk).

.EXAMPLE
  # 1) Create secret once (replace with your key):
  #   $key = Read-Host -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($key)) | gcloud secrets versions add openai-api-key --data-file=-

  .\scripts\deploy_cloud_run.ps1 -Region us-central1 -MinInstances 1 -SecretName openai-api-key `
    -CloudSqlInstance "test1-493607:us-central1:medical-vectors-db-new" -DatabaseUrlSecretName database-url

  # Create DATABASE_URL secret once (Unix socket form for Cloud Run + Cloud SQL):
  #   echo -n "postgresql://USER:PASS@/postgres?host=/cloudsql/PROJECT:REGION:INSTANCE" | gcloud secrets create database-url --data-file=-
#>
[CmdletBinding()]
param(
    [string] $Project = "",
    [string] $Region = "us-central1",
    [string] $Service = "medical-cost-api",
    [int] $MinInstances = 1,
    # 4Gi x 5 max fits common Cloud Run regional memory quota; increase after quota bump.
    [int] $MaxInstances = 5,
    [string] $Memory = "4Gi",
    [string] $Cpu = "2",
    [int] $TimeoutSeconds = 300,
    [int] $Concurrency = 20,
    [string] $SecretName = "",
    [string] $OpenAiApiKey = "",
    [string] $CloudSqlInstance = "",
    [string] $DatabaseUrlSecretName = "",
    [bool] $AllowUnauthenticated = $true,
    [switch] $WhatIf
)

$ErrorActionPreference = "Stop"
# scripts\deploy_cloud_run.ps1 -> repo root is parent of scripts
$Root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path (Join-Path $Root "app\main.py"))) {
    throw "Could not find app\main.py under repo root: $Root"
}

if (-not $Project) {
    $Project = gcloud config get-value project 2>$null
}
if (-not $Project) {
    throw "Set GCP project: gcloud config set project YOUR_PROJECT_ID"
}

Write-Host "Project : $Project"
Write-Host "Region  : $Region"
Write-Host "Service : $Service"
Write-Host "Root    : $Root"

$apis = @(
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com"
)
if (-not $WhatIf) {
    gcloud services enable @apis --project $Project
}

$repo = "cloud-run-source"
$ar = gcloud artifacts repositories describe $repo --location $Region --project $Project 2>$null
if (-not $ar -and -not $WhatIf) {
    gcloud artifacts repositories create $repo `
        --repository-format=docker `
        --location=$Region `
        --description="Cloud Run builds" `
        --project=$Project
}

$envVars = "PRELOAD_FAISS=true,LOG_LEVEL=INFO,ENVIRONMENT=production"
if ($OpenAiApiKey -and -not $SecretName) {
    $envVars += ",OPENAI_API_KEY=$OpenAiApiKey"
}

$runArgs = @(
    "run", "deploy", $Service,
    "--project", $Project,
    "--region", $Region,
    "--source", $Root,
    "--platform", "managed",
    "--memory", $Memory,
    "--cpu", $Cpu,
    "--min-instances", $MinInstances.ToString(),
    "--max-instances", $MaxInstances.ToString(),
    "--timeout", $TimeoutSeconds.ToString(),
    "--concurrency", $Concurrency.ToString(),
    "--set-env-vars", $envVars
)

if ($CloudSqlInstance) {
    $runArgs += "--add-cloudsql-instances", $CloudSqlInstance
}

if ($AllowUnauthenticated) {
    $runArgs += "--allow-unauthenticated"
}
else {
    $runArgs += "--no-allow-unauthenticated"
}

$secretPairs = @()
if ($SecretName) {
    $secretPairs += "OPENAI_API_KEY=${SecretName}:latest"
}
if ($DatabaseUrlSecretName) {
    $secretPairs += "DATABASE_URL=${DatabaseUrlSecretName}:latest"
}
if ($secretPairs.Count -gt 0) {
    $runArgs += "--set-secrets", ($secretPairs -join ",")
}
elseif (-not $OpenAiApiKey) {
    Write-Warning "No -SecretName / -OpenAiApiKey: ensure OPENAI_API_KEY exists on the service (Secret Manager or env)."
}

if ($WhatIf) {
    Write-Host "[WhatIf] gcloud $($runArgs -join ' ')"
    exit 0
}

Push-Location $Root
try {
    & gcloud @runArgs
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Done. Get URL:"
Write-Host "  gcloud run services describe $Service --region $Region --project $Project --format='value(status.url)'"
