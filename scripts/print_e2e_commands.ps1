# =============================================================================
# QuantLab — Print the browser E2E commands (Phase 43.0)
#
# PRINT-ONLY. This script NEVER: runs tests, starts servers, runs npm run
# dev/build or next dev/build, installs dependencies or browsers, deletes
# files, changes execution policy, calls external APIs, creates tags, pushes,
# or deploys.
# =============================================================================

Write-Host ""
Write-Host "=== QuantLab browser E2E — command cheat sheet ===" -ForegroundColor Cyan
Write-Host "(E2E green is a frozen-demo regression signal, not a certification)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "1) Start the servers yourself first (in separate terminals):" -ForegroundColor Cyan
Write-Host "   cd C:\quantlab\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000"
Write-Host "   cd C:\quantlab\frontend; npm run dev          # dev  -> http://localhost:3000"
Write-Host "   # or production:  npm run build; npx next start --port 3100"
Write-Host ""
Write-Host "2) Run the harness (from C:\quantlab\frontend):" -ForegroundColor Cyan
Write-Host "   npm run e2e              # everything"
Write-Host "   npm run e2e:frozen       # frozen demo + Scenario Studio + KO/PEP pairs"
Write-Host "   npm run e2e:responsive   # 1440 / 1024 / 768 geometry guards"
Write-Host ""
Write-Host "3) Against the production server instead of dev:" -ForegroundColor Cyan
Write-Host "   `$env:E2E_BASE_URL = 'http://localhost:3100'; npm run e2e"
Write-Host ""
Write-Host "4) Open the HTML report:" -ForegroundColor Cyan
Write-Host "   npm run e2e:report"
Write-Host ""
Write-Host "Artifacts land in C:\quantlab\artifacts\e2e\ (gitignored)." -ForegroundColor DarkGray
Write-Host "Frozen evidence in docs\screenshots\release_*.png is never written." -ForegroundColor DarkGray
Write-Host "Docs: docs\BROWSER_E2E_RUNBOOK.md · docs\PLAYWRIGHT_SETUP.md" -ForegroundColor DarkGray
Write-Host ""
exit 0
