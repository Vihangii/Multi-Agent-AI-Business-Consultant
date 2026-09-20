# Launches the Multi-Agent AI Business Consultant: FastAPI backend + Next.js web app.
#
#   .\run.ps1              # API + web app, each in its own window
#   .\run.ps1 -ApiOnly     # just the API (e.g. to use the REST endpoints / docs)
#   .\run.ps1 -Port 8010   # pick the API port explicitly
#
# Runs from any directory - it always uses the project root.

param(
    [switch]$ApiOnly,
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$web = Join-Path $root "web"

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

# Pick the API port: explicit -Port, else BACKEND_PORT from .env, else 8000.
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
$apiUrl = "http://localhost:$Port"

Write-Host ""
Write-Host "  API       ->  $apiUrl   (docs at $apiUrl/docs, metrics at $apiUrl/metrics)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$root'; `$env:PYTHONUTF8=1; & '$python' -m uvicorn backend.main:app --reload --port $Port"
) -WindowStyle Normal

if (-not $ApiOnly) {
    if (-not (Test-Path (Join-Path $web "node_modules"))) {
        Write-Host "Installing web dependencies (npm install)..." -ForegroundColor Yellow
        Push-Location $web; npm install --no-audit --no-fund; Pop-Location
    }
    $envLocal = Join-Path $web ".env.local"
    if (-not (Test-Path $envLocal)) { Copy-Item (Join-Path $web ".env.example") $envLocal }

    $webPort = 3000
    while (-not (Test-PortFree $webPort)) { $webPort++ }
    Write-Host "  Web app   ->  http://localhost:$webPort" -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$web'; `$env:NEXT_PUBLIC_API_URL='$apiUrl'; npm run dev -- --port $webPort"
    ) -WindowStyle Normal
}

Write-Host ""
Write-Host "Starting... close the window(s) to stop." -ForegroundColor Green
