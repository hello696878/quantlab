# =============================================================================
# QuantLab — Run the backend dev server (Phase 39.0)
#
# Starts uvicorn on port 8000 using the repo's venv (backend\venv, with .venv
# as an alternate). Prints exactly what it will run before running it.
#
# This script NEVER: installs dependencies, touches the frontend, downloads
# anything, changes execution policy, or requires admin. Stop with Ctrl+C.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"

if (-not (Test-Path (Join-Path $backendDir "app\main.py"))) {
    Write-Host "[ERROR] backend\app\main.py not found under $backendDir — run this from the QuantLab repo." -ForegroundColor Red
    exit 1
}

$venvCandidates = @(
    (Join-Path $backendDir "venv\Scripts\python.exe"),
    (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$python = $venvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($null -eq $python) {
    Write-Host "[WARN] No venv Python found (looked for backend\venv and .venv)." -ForegroundColor Yellow
    Write-Host "       Falling back to 'python' on PATH — dependencies may be missing." -ForegroundColor Yellow
    Write-Host "       To set up (yourself): python -m venv backend\venv; backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt" -ForegroundColor Yellow
    $python = "python"
}

Write-Host "About to run (Ctrl+C to stop):" -ForegroundColor Cyan
Write-Host ("  cd {0}" -f $backendDir)
Write-Host ("  {0} -m uvicorn app.main:app --reload --port 8000" -f $python)
Write-Host ""

Set-Location $backendDir
& $python -m uvicorn app.main:app --reload --port 8000
exit $LASTEXITCODE
