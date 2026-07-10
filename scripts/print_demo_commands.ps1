# =============================================================================
# QuantLab — Print the demo command cheat-sheet (Phase 39.0)
#
# PRINT-ONLY. Shows the commands you run yourself for a local demo, plus the
# suggested demo route. Runs nothing, changes nothing, fetches nothing.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "QuantLab — local demo cheat-sheet (all commands are run by YOU; this script only prints)" -ForegroundColor Cyan
Write-Host ("Repo root: {0}" -f $repoRoot)
Write-Host ""
Write-Host "1) Backend dev server:" -ForegroundColor Green
Write-Host "     cd $repoRoot\backend"
Write-Host "     venv\Scripts\uvicorn app.main:app --reload --port 8000"
Write-Host ""
Write-Host "2) Frontend dev server (user-run):" -ForegroundColor Green
Write-Host "     cd $repoRoot\frontend"
Write-Host "     npm run dev"
Write-Host ""
Write-Host "3) Backend tests:" -ForegroundColor Green
Write-Host "     cd $repoRoot"
Write-Host "     backend\venv\Scripts\python.exe -m pytest backend\tests -q"
Write-Host ""
Write-Host "4) Frontend typecheck:" -ForegroundColor Green
Write-Host "     cd $repoRoot\frontend"
Write-Host "     npx tsc --noEmit"
Write-Host ""
Write-Host "5) Production build (user-run):" -ForegroundColor Green
Write-Host "     cd $repoRoot\frontend"
Write-Host "     npm run build"
Write-Host ""
Write-Host "Suggested demo route (see docs/LOCAL_DEMO_GUIDE.md):" -ForegroundColor Cyan
Write-Host "     Portfolio Showcase -> Demo Center -> Scenario Studio -> Research Workspace"
Write-Host "     -> Data Reliability Center -> QA Command Center"
Write-Host ""
Write-Host "Ground rules: deterministic educational sample data; no live trading;" -ForegroundColor DarkGray
Write-Host "not investment advice; not production compliance infrastructure." -ForegroundColor DarkGray
exit 0
