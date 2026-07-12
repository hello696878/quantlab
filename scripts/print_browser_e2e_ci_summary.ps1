# =============================================================================
# QuantLab — Print the manual CI browser E2E summary (Phase 45.0)
#
# PRINT-ONLY. This script NEVER: invokes GitHub APIs, triggers workflows,
# runs tests or builds, starts servers, installs packages, creates
# commits/tags, pushes, deploys, deletes files, or prints secrets.
# =============================================================================

Write-Host ""
Write-Host "=== QuantLab manual CI browser E2E (Browser E2E Preflight) ===" -ForegroundColor Cyan
Write-Host "(a regression signal on one commit - never a certification)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Workflow file    : .github\workflows\browser-e2e.yml"
Write-Host "Trigger          : workflow_dispatch ONLY (manual, from the Actions tab; no push/PR gate)"
Write-Host "Permissions      : contents: read (no secrets, no publishing, no deployment)"
Write-Host "Runner           : ubuntu-latest, Python 3.11, Node 20, Playwright Chromium (runner-only install)"
Write-Host ""
Write-Host "Local equivalent (servers must already be running):" -ForegroundColor Cyan
Write-Host "  backend  : http://localhost:8000   (uvicorn)"
Write-Host "  frontend : http://localhost:3000 dev, or build + next start on :3100"
Write-Host "  cd frontend; npx playwright test --project=chromium"
Write-Host ""
Write-Host "Generated evidence paths:" -ForegroundColor Cyan
Write-Host "  local : artifacts\e2e\  (gitignored, disposable)"
Write-Host "  CI    : workflow artifact browser-e2e-evidence-<run id> (14-day retention)"
Write-Host "          contains artifacts/e2e + backend.log/frontend.log from artifacts/e2e-ci"
Write-Host ""
Write-Host "To run it on GitHub (manual, every time):" -ForegroundColor Cyan
Write-Host "  repo -> Actions -> 'Browser E2E Preflight' -> Run workflow -> main -> Run workflow"
Write-Host "  then record: run ID, commit SHA, per-step conclusions, artifact name."
Write-Host ""
Write-Host "Reminders: docs/CI_BROWSER_E2E.md says 'Not yet run' until YOU observe a real" -ForegroundColor DarkGray
Write-Host "run; never claim green without a run ID. Frozen screenshots are separate and" -ForegroundColor DarkGray
Write-Host "untouched. Deterministic fixtures only; no live data; no secrets." -ForegroundColor DarkGray
Write-Host ""
exit 0
