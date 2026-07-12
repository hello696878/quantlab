# =============================================================================
# QuantLab — Print the public GitHub launch summary (Phase 46.0)
#
# PRINT-ONLY. Reads local git state and prints the launch documents and
# user-run commands. This script NEVER: creates tags, pushes, calls GitHub
# APIs, creates releases, triggers workflows, runs tests/builds, starts
# servers, installs packages, deletes or modifies files, prints secrets, or
# opens a browser.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host ""
Write-Host "=== QuantLab public GitHub launch summary (v4.64) ===" -ForegroundColor Cyan
Write-Host "(manual publication only - not a certification of anything)" -ForegroundColor DarkGray
Write-Host ""
$branch = git rev-parse --abbrev-ref HEAD 2>$null
$head = git log -1 --oneline 2>$null
Write-Host "Branch : $branch"
Write-Host "HEAD   : $head"
Write-Host ""
Write-Host "Milestone tags (local):" -ForegroundColor Cyan
git tag --list "v4.6[0-4]*" | ForEach-Object { Write-Host "  $_" }
Write-Host "  target (user-created after review): v4.64.0-public-github-release-launch-v1"
Write-Host ""
Write-Host "Launch documents:" -ForegroundColor Cyan
$docs = @(
    "docs\GITHUB_RELEASE_FINAL_v4.64.md",
    "docs\RELEASE_EVIDENCE_v4.64.md",
    "docs\PUBLIC_GITHUB_LAUNCH_CHECKLIST.md",
    "docs\RELEASE_CHECKSUMS_v4.64.sha256"
)
foreach ($d in $docs) {
    $tag = if (Test-Path (Join-Path $repoRoot $d)) { "[found] " } else { "[MISSING]" }
    Write-Host "  $tag $d"
}
Write-Host ""
Write-Host "User-run verification (NOT run by this script):" -ForegroundColor Cyan
Write-Host "  backend\venv\Scripts\python.exe scripts\verify_release_checksums.py docs\RELEASE_CHECKSUMS_v4.64.sha256"
Write-Host "  backend\venv\Scripts\python.exe -m pytest backend\tests -q"
Write-Host "  cd frontend; npx tsc --noEmit"
Write-Host "  cd frontend; npx playwright test --list --project=chromium"
Write-Host "  cd frontend; npx playwright test --project=chromium   # servers running"
Write-Host ""
Write-Host "Before publishing:" -ForegroundColor DarkGray
Write-Host "  - Normal CI AND Browser E2E Preflight must be green on the release commit" -ForegroundColor DarkGray
Write-Host "  - Follow docs\PUBLIC_GITHUB_LAUNCH_CHECKLIST.md end to end" -ForegroundColor DarkGray
Write-Host "  - The GitHub Release is created MANUALLY from docs\GITHUB_RELEASE_FINAL_v4.64.md" -ForegroundColor DarkGray
Write-Host ""
exit 0
