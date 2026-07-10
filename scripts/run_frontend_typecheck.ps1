# =============================================================================
# QuantLab — Frontend typecheck (Phase 39.0)
#
# Runs `npx tsc --noEmit` in frontend\. This is a typecheck only — it NEVER
# runs `npm run dev`, `npm run build`, installs packages, or uses the network
# beyond what npx itself resolves locally (tsc is already in node_modules).
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"

if (-not (Test-Path (Join-Path $frontendDir "package.json"))) {
    Write-Host "[ERROR] frontend\package.json not found — run this from the QuantLab repo." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[WARN] frontend\node_modules missing — run (yourself): cd frontend; npm install" -ForegroundColor Yellow
}
if ($null -eq (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] npx not found on PATH — install Node 18+ first." -ForegroundColor Red
    exit 1
}

Write-Host "About to run:" -ForegroundColor Cyan
Write-Host ("  cd {0}" -f $frontendDir)
Write-Host "  npx tsc --noEmit"
Write-Host ""

Set-Location $frontendDir
npx tsc --noEmit
$code = $LASTEXITCODE
if ($code -eq 0) {
    Write-Host "Typecheck passed (exit 0)." -ForegroundColor Green
} else {
    Write-Host ("Typecheck reported errors (exit {0}) — shown above, not hidden." -f $code) -ForegroundColor Yellow
}
exit $code
