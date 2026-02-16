param(
    [string]$Token,
    [string]$Owner = 'Bharatoberoi',
    [string]$Repo = 'healthcareapp',
    [string]$Head = 'gke-monitoring',
    [string]$Base = 'main'
)

if (-not $Token) { Write-Host 'Missing token'; exit 1 }

$body = @{ title = 'Add GKE + monitoring + CI'; head = $Head; base = $Base; body = 'Adds GKE cluster scripts, FAISS preload, readiness, Prometheus/OpenTelemetry instrumentation, Helm monitoring install, and GitHub Actions CI.' } | ConvertTo-Json

try {
    $url = "https://api.github.com/repos/$Owner/$Repo/pulls"
    $resp = Invoke-RestMethod -Headers @{ Authorization = "token $Token" } -Uri $url -Method Post -Body $body -ContentType 'application/json' -ErrorAction Stop
    Write-Host $resp.html_url
} catch {
    Write-Host 'PR create failed:' $_.Exception.Message
    exit 1
}