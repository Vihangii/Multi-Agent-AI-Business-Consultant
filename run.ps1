# Starts the FastAPI backend and the Streamlit dashboard together.
#
#   .\run.ps1            # from the project root
#   .\run.ps1 -Port 8010 # pick the backend port explicitly
#
# Backend and frontend each get their own window; close them (or Ctrl+C in
# each) to stop. Runs from any directory - it always uses the project root.

param(
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "No virtualenv found. Creating one with Python 3.12 and installing dependencies..." -ForegroundColor Yellow
    py -3.12 -m venv (Join-Path $root ".venv")
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r (Join-Path $root "requirements.txt")
}

if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Host "Created .env from .env.example - add your OPENAI_API_KEY there to enable AI recommendations." -ForegroundColor Yellow
}

# Pick the backend port: explicit -Port, else BACKEND_PORT from .env, else 8000.
if ($Port -eq 0) {
    $envPort = (Get-Content (Join-Path $root ".env") | Where-Object { $_ -match '^\s*BACKEND_PORT\s*=\s*(\d+)' } | ForEach-Object { $Matches[1] } | Select-Object -First 1)
    $Port = if ($envPort) { [int]$envPort } else { 8000 }
}

# If that port is busy (e.g. another project's server), move to the next free one.
function Test-PortFree([int]$p) {
    -not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}
$requested = $Port
while (-not (Test-PortFree $Port)) { $Port++ }
if ($Port -ne $requested) {
    Write-Host "Port $requested is in use by another process - using $Port instead." -ForegroundColor Yellow
}

$backendUrl = "http://localhost:$Port"

Write-Host ""
Write-Host "  Backend   ->  $backendUrl   (docs at $backendUrl/docs)" -ForegroundColor Cyan
Write-Host "  Dashboard ->  http://localhost:8501" -ForegroundColor Cyan
Write-Host ""

# Backend window
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root'; `$env:PYTHONUTF8=1; & '$python' -m uvicorn backend.main:app --reload --port $Port"
) -WindowStyle Normal

# Give uvicorn a moment so the dashboard's first health check succeeds
Start-Sleep -Seconds 2

# Frontend window - BACKEND_URL tells the dashboard where the API is
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root'; `$env:PYTHONUTF8=1; `$env:BACKEND_URL='$backendUrl'; & '$python' -m streamlit run frontend/app.py --server.port 8501"
) -WindowStyle Normal

Write-Host "Both servers are starting in separate windows. The dashboard will open in your browser shortly." -ForegroundColor Green
