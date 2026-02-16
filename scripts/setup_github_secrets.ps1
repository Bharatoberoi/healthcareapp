param(
    [Parameter(Mandatory=$true)]
    [string]$Project,
    
    [string]$Cluster = "service-code-cluster",
    
    [Parameter(Mandatory=$true)]
    [string]$Zone,
    
    [Parameter(Mandatory=$true)]
    [string]$KeyFile
)

# Ensure GitHub CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed. Please install it from https://cli.github.com/"
    exit 1
}

# Check if authenticated
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not authenticated with GitHub CLI. Run 'gh auth login' first."
    exit 1
}

# Verify service account key file exists
if (-not (Test-Path $KeyFile)) {
    Write-Error "Service account key file not found: $KeyFile"
    exit 1
}

Write-Host "Setting up GitHub repository secrets..." -ForegroundColor Green

# Set GKE_CLUSTER
Write-Host "Setting GKE_CLUSTER = $Cluster"
echo $Cluster | gh secret set GKE_CLUSTER
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set GKE_CLUSTER secret"
    exit 1
}

# Set GCP_PROJECT
Write-Host "Setting GCP_PROJECT = $Project"
echo $Project | gh secret set GCP_PROJECT
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set GCP_PROJECT secret"
    exit 1
}

# Set GKE_ZONE
Write-Host "Setting GKE_ZONE = $Zone"
echo $Zone | gh secret set GKE_ZONE
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set GKE_ZONE secret"
    exit 1
}

# Set GCP_SA_KEY
Write-Host "Setting GCP_SA_KEY from $KeyFile"
Get-Content $KeyFile | gh secret set GCP_SA_KEY
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set GCP_SA_KEY secret"
    exit 1
}

Write-Host "`nAll secrets set successfully!" -ForegroundColor Green
Write-Host "`nVerifying secrets..."
gh secret list

Write-Host "`nSetup complete! You can now run the CI/CD workflow." -ForegroundColor Green
