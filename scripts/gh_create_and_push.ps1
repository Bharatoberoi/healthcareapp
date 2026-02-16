param(
    [string]$Token
)

if (-not $Token) {
    Write-Host "No token provided. Exiting."; exit 1
}
$env:GITHUB_TOKEN = $Token

try {
    Write-Host "Creating repository 'service-code-resolution' under authenticated user..."
    $body = @{ name = 'service-code-resolution'; private = $false; description = 'GKE + FAISS nodepool scripts, readiness, monitoring & CI' } | ConvertTo-Json
    $repo = Invoke-RestMethod -Headers @{ Authorization = "token $env:GITHUB_TOKEN" } -Uri 'https://api.github.com/user/repos' -Method Post -Body $body -ContentType 'application/json' -ErrorAction Stop
    Write-Host "Created repo: $($repo.full_name) -> $($repo.html_url)"
} catch {
    Write-Host "Repo create error: $($_.Exception.Message)"
    exit 1
}

if (-not (Test-Path .git)) { git init }

git checkout -b gke-monitoring

git add .

git config user.email 'copilot@example.com'
git config user.name 'GitHub Copilot'

git commit -m 'chore: add GKE + FAISS nodepool scripts, readiness, monitoring & CI' 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host 'No changes to commit or commit failed' }

$pushUrl = $repo.clone_url -replace 'https://', "https://$($env:GITHUB_TOKEN)@"
Write-Host "Pushing branch gke-monitoring to GitHub..."

git push $pushUrl gke-monitoring:refs/heads/gke-monitoring -u

# Create PR
$prBody = @{ title = 'Add GKE + monitoring + CI'; head = 'gke-monitoring'; base = 'main'; body = 'Automatic PR: adds GKE cluster scripts, nodepool guidance, FAISS preload, readiness, Prometheus + OpenTelemetry instrumentation, Helm monitoring install, and GitHub Actions CI.' } | ConvertTo-Json
try {
    $pr = Invoke-RestMethod -Headers @{ Authorization = "token $env:GITHUB_TOKEN" } -Uri ("https://api.github.com/repos/" + $repo.full_name + "/pulls") -Method Post -Body $prBody -ContentType 'application/json' -ErrorAction Stop
    Write-Host "PR created: $($pr.html_url)"
} catch {
    Write-Host "PR create error: $($_.Exception.Message)"
    exit 1
}
