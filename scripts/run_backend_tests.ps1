# =============================================================================
# QuantLab — Run the backend test suite (Phase 39.0)
#
# Removes the throwaway repo-root artifacts\ folder if present (the only
# mutation, and only that exact path), then runs pytest via the repo venv
# (backend\venv, with .venv as an alternate; falls back to 'python' on PATH).
#
# This script NEVER: installs dependencies, uses the network, starts servers,
# changes execution policy, or requires admin. Test results are printed
# as-is — failures are never hidden.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$artifacts = Join-Path $repoRoot "artifacts"
if (Test-Path $artifacts) {
    Write-Host ("Removing throwaway folder: {0}" -f $artifacts) -ForegroundColor Yellow
    Remove-Item -Recurse -Force $artifacts
}

$venvCandidates = @(
    (Join-Path $repoRoot "backend\venv\Scripts\python.exe"),
    (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$python = $venvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($null -eq $python) {
    Write-Host "[WARN] No venv Python found — falling back to 'python' on PATH (pytest may be missing)." -ForegroundColor Yellow
    $python = "python"
}

Write-Host "About to run:" -ForegroundColor Cyan
Write-Host ("  {0} -m pytest backend\tests -q" -f $python)
Write-Host ""

& $python -m pytest backend\tests -q
$code = $LASTEXITCODE

Write-Host ""
if (Test-Path $artifacts) {
    Write-Host "[WARN] artifacts\ exists after the run — it should not; please delete it and investigate." -ForegroundColor Yellow
} else {
    Write-Host "artifacts\ absent after the run (as expected)." -ForegroundColor DarkGray
}
exit $code
