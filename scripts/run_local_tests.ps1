# Run full API scenario tests against a local uvicorn instance.
#
# Before running:
#   1. app\.env  -> OPENAI_API_KEY, DATABASE_URL (pgvector)
#   2. If DATABASE_URL uses 127.0.0.1:5432 -> start Cloud SQL Auth Proxy first
#   3. Start API:  uvicorn app.main:app --host 127.0.0.1 --port 8000
#
# If auth fails with user "u" or wrong DB: a User/System DATABASE_URL env var
# overrides app\.env. Remove it in Windows "Environment Variables" or run:
#   Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
#
# Optional:  $env:API_BASE_URL = "http://127.0.0.1:8000"

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host "Prereqs: Cloud SQL proxy (if using 127.0.0.1:5432) + uvicorn on API_BASE_URL (default http://127.0.0.1:8000)" -ForegroundColor Cyan
python run_tests.py
