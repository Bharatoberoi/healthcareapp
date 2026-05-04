# Start Cloud SQL Auth Proxy so DATABASE_URL can use 127.0.0.1:5432
#
# Prerequisites:
#   1. Install Cloud SQL Auth Proxy: https://cloud.google.com/sql/docs/postgres/connect-auth-proxy
#   2. gcloud auth application-default login
#   3. Enable API: gcloud services enable sqladmin.googleapis.com --project=YOUR_PROJECT_ID
#
# Usage:
#   .\scripts\start_cloud_sql_proxy.ps1 -InstanceConnectionName "my-project:us-central1:my-instance"
#
# Then in another terminal set DATABASE_URL, e.g.:
#   $env:DATABASE_URL = "postgresql://APP_USER:PASSWORD@127.0.0.1:5432/medical_vectors"
#   python scripts/load_faiss_into_pgvector.py

param(
    [Parameter(Mandatory = $true)]
    [string] $InstanceConnectionName
)

$proxy = Get-Command cloud-sql-proxy -ErrorAction SilentlyContinue
if (-not $proxy) {
    Write-Error "cloud-sql-proxy not found on PATH. Install from: https://cloud.google.com/sql/docs/postgres/sql-proxy"
    exit 1
}

Write-Host "Listening on 127.0.0.1:5432 -> $InstanceConnectionName" -ForegroundColor Cyan
& cloud-sql-proxy $InstanceConnectionName --port 5432
