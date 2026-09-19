# Launches the Multi-Agent AI Business Consultant.
#
#   .\run.ps1              # dashboard only - runs the agents in-process (default)
#   .\run.ps1 -WithApi     # also start the FastAPI server in a second window
#   .\run.ps1 -WithApi -Port 8010
#
# Runs from any directory - it always uses the project root.

param(
    [switch]$WithApi,
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

function Test-PortFree([int]$p) {
    -not (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

$frontendEnv = "`$env:PYTHONUTF8=1"

if ($WithApi) {
    # Pick the backend port: explicit -Port, else BACKEND_PORT from .env, else 8000.
    if ($Port -eq 0) {
        $envPort = (Get-Content (Join-Path $root ".env") | Where-Object { $_ -match '^\s*BACKEND_PORT\s*=\s*(\d+)' } | ForEach-Object { $Matches[1] } | Select-Object -First 1)
        $Port = if ($envPort) { [int]$envPort } else { 8000 }
    }
    # If that port is busy (e.g. another project's server), move to the next free one.
    $requested = $Port
    while (-not (Test-PortFree $Port)) { $Port++ }
    if ($Port -ne $requested) {
        Write-Host "Port $requested is in use by another process - using $Port instead." -ForegroundColor Yellow
    }
    $backendUrl = "http://localhost:$Port"

    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$root'; `$env:PYTHONUTF8=1; & '$python' -m uvicorn backend.main:app --reload --port $Port"
    ) -WindowStyle Normal
    Start-Sleep -Seconds 2

    $frontendEnv += "; `$env:BACKEND_MODE='remote'; `$env:BACKEND_URL='$backendUrl'"
    Write-Host ""
    Write-Host "  API       ->  $backendUrl   (docs at $backendUrl/docs)" -ForegroundColor Cyan
}

Write-Host "  Dashboard ->  http://localhost:8501" -ForegroundColor Cyan
Write-Host ""

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root'; $frontendEnv; & '$python' -m streamlit run frontend/app.py --server.port 8501"
) -WindowStyle Normal

Write-Host "Starting... the dashboard will open in your browser shortly. Close the window(s) to stop." -ForegroundColor Green
