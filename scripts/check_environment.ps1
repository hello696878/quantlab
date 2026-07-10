# =============================================================================
# QuantLab — Environment Doctor (Phase 39.0)
#
# READ-ONLY. Checks that the local toolchain looks ready for a QuantLab demo:
# Python, the backend venv, backend/frontend dependency markers, Node/npm,
# and (best-effort) whether ports 8000/3000 look busy.
#
# This script NEVER: installs anything, starts servers, runs dev/build,
# downloads anything, changes execution policy, requires admin, or writes to
# the repository. It reports what it sees; fixing anything is your call.
# See docs/ENVIRONMENT_DOCTOR.md for how to read the output.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
$results = New-Object System.Collections.Generic.List[string]
$problems = 0

function Report {
    param([bool]$Ok, [string]$Label, [string]$Detail)
    $tag = if ($Ok) { "[ OK ]" } else { "[MISS]" }
    $color = if ($Ok) { "Green" } else { "Yellow" }
    Write-Host ("{0} {1}" -f $tag, $Label) -ForegroundColor $color
    if ($Detail) { Write-Host ("       {0}" -f $Detail) -ForegroundColor DarkGray }
    $script:results.Add(("{0} {1}" -f $tag, $Label))
    if (-not $Ok) { $script:problems++ }
}

Write-Host "QuantLab Environment Doctor (read-only)" -ForegroundColor Cyan
Write-Host ("Repo root: {0}" -f $repoRoot)
Write-Host ""

# --- Python -----------------------------------------------------------------
$sysPython = Get-Command python -ErrorAction SilentlyContinue
Report ($null -ne $sysPython) "System Python on PATH" $(if ($sysPython) { $sysPython.Source } else { "Install Python 3.11+ or rely on the venv below." })

# --- Backend venv (this repo uses backend\venv; .venv is an alternate) ------
$venvCandidates = @(
    (Join-Path $repoRoot "backend\venv\Scripts\python.exe"),
    (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$venvPython = $venvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
Report ($null -ne $venvPython) "Backend venv Python" $(if ($venvPython) { $venvPython } else { "Expected at backend\venv\Scripts\python.exe — see docs/DEVELOPER_ONBOARDING.md." })

# --- Backend dependency markers (presence checks, not correctness) ----------
Report (Test-Path (Join-Path $repoRoot "backend\requirements.txt")) "backend\requirements.txt exists" ""
Report (Test-Path (Join-Path $repoRoot "backend\app\main.py")) "backend\app\main.py exists" ""
if ($venvPython) {
    # Import probes run locally inside the venv; they fetch nothing.
    $probe = & $venvPython -c "import fastapi, pydantic, pytest; print('ok')" 2>$null
    Report ($probe -eq "ok") "venv imports fastapi/pydantic/pytest" $(if ($probe -ne "ok") { "Run (yourself): backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt" } else { "" })
}

# --- Node / npm / frontend deps ---------------------------------------------
$node = Get-Command node -ErrorAction SilentlyContinue
Report ($null -ne $node) "Node on PATH" $(if ($node) { (& node --version) } else { "Install Node 18+." })
$npm = Get-Command npm -ErrorAction SilentlyContinue
Report ($null -ne $npm) "npm on PATH" $(if ($npm) { "npm " + (& npm --version) } else { "" })
Report (Test-Path (Join-Path $repoRoot "frontend\package.json")) "frontend\package.json exists" ""
Report (Test-Path (Join-Path $repoRoot "frontend\node_modules")) "frontend\node_modules installed" $(if (-not (Test-Path (Join-Path $repoRoot "frontend\node_modules"))) { "Run (yourself): cd frontend; npm install" } else { "" })

# --- Docs --------------------------------------------------------------------
Report (Test-Path (Join-Path $repoRoot "docs\LOCAL_DEMO_GUIDE.md")) "docs\LOCAL_DEMO_GUIDE.md exists" ""
Report (Test-Path (Join-Path $repoRoot "docs\TROUBLESHOOTING.md")) "docs\TROUBLESHOOTING.md exists" ""

# --- Port hints (best-effort, read-only; may be unavailable on some setups) --
foreach ($port in 8000, 3000) {
    try {
        $inUse = $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
        $label = "Port $port " + $(if ($inUse) { "is already LISTENING (something is running there)" } else { "looks free" })
        Write-Host ("[HINT] {0}" -f $label) -ForegroundColor DarkCyan
    } catch {
        Write-Host ("[HINT] Could not check port {0} (that's fine — informational only)" -f $port) -ForegroundColor DarkCyan
    }
}

# --- Summary ------------------------------------------------------------------
Write-Host ""
if ($problems -eq 0) {
    Write-Host "Summary: all checks passed. Next steps (run yourself):" -ForegroundColor Green
} else {
    Write-Host ("Summary: {0} check(s) need attention (see [MISS] lines above)." -f $problems) -ForegroundColor Yellow
    Write-Host "Suggested next steps once resolved (run yourself):" -ForegroundColor Yellow
}
Write-Host "  Backend:   .\scripts\run_backend.ps1"
Write-Host "  Frontend:  cd frontend; npm run dev        (user-run; never run by scripts)"
Write-Host "  Tests:     .\scripts\run_backend_tests.ps1"
Write-Host "  Typecheck: .\scripts\run_frontend_typecheck.ps1"
Write-Host ""
Write-Host "Note: these are presence checks, not proof anything runs correctly —" -ForegroundColor DarkGray
Write-Host "run the tests and typecheck yourself to verify. No network was used." -ForegroundColor DarkGray

exit $(if ($problems -eq 0) { 0 } else { 1 })
