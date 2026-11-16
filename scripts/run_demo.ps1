# One-shot launcher for the demo: backend + Cloudflare quick tunnel.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
# Requires: .venv prepared, cloudflared.exe in the project root.
param(
    [int]$Port = 8000,
    [string]$LlmKey = $env:LLM_API_KEY
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $LlmKey) {
    Write-Host "[warn] LLM_API_KEY is empty, backend will fall back to mock provider."
}

$env:LLM_API_KEY = $LlmKey
$env:PYTHONPATH = Join-Path $root "apps\api"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv not found: $python" }

$db = Join-Path $root "data\agentdesk.db"
if (-not (Test-Path $db)) {
    Write-Host "[info] seeding demo data ..."
    & $python "apps\api\seed\demo.py"
}

Write-Host "[info] starting backend on 127.0.0.1:$Port ..."
$api = Start-Process -FilePath $python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $Port `
    -WorkingDirectory (Join-Path $root "apps\api") -PassThru -WindowStyle Minimized

Start-Sleep -Seconds 4
try {
    $health = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/api/health" -TimeoutSec 10
    Write-Host "[ok] health: $($health.Content)"
} catch {
    Write-Host "[warn] health check failed, check the backend window."
}

$cloudflared = Join-Path $root "cloudflared.exe"
if (Test-Path $cloudflared) {
    Write-Host "[info] opening public tunnel, grab the trycloudflare.com URL from below ..."
    & $cloudflared tunnel --url "http://127.0.0.1:$Port" --no-autoupdate
} else {
    Write-Host "[info] cloudflared.exe not found, local only: http://127.0.0.1:$Port"
}

if ($api -and -not $api.HasExited) { $api | Stop-Process -Force }
