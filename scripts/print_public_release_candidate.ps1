# =============================================================================
# QuantLab — Print the public release candidate summary (Phase 42.0)
#
# PRINT-ONLY. Reads local git state and prints the RC doc paths and the
# user-run verification commands. This script NEVER: runs builds or dev
# servers, runs tests, creates tags, commits or pushes, calls the GitHub API,
# deploys, installs packages, deletes files, changes execution policy, or
# touches secrets.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host ""
Write-Host "=== QuantLab Public Release Candidate v1 ===" -ForegroundColor Cyan
Write-Host "(public portfolio readiness only - not a production certification)" -ForegroundColor DarkGray
Write-Host ""

# --- Local git state (read-only) ---------------------------------------------
$branch = git rev-parse --abbrev-ref HEAD 2>$null
$commit = git log -1 --oneline 2>$null
$versionFile = Join-Path $repoRoot "VERSION"
$versionLabel = if (Test-Path $versionFile) { (Get-Content $versionFile -TotalCount 1).Trim() } else { "(VERSION file not found)" }

Write-Host "Current branch : $branch"
Write-Host "Latest commit  : $commit"
Write-Host "Version label  : $versionLabel"
Write-Host ""

# --- RC documents --------------------------------------------------------------
Write-Host "Release candidate documents:" -ForegroundColor Cyan
$rcDocs = @(
    "docs\PUBLIC_RELEASE_CANDIDATE.md      (required checks + status table)",
    "docs\FINAL_SMOKE_TEST_RUNBOOK.md      (page-by-page manual pass)",
    "docs\DEMO_FREEZE_CHECKLIST.md         (freeze date/commit/tag + do-not-change list)",
    "docs\PUBLIC_LAUNCH_READINESS.md       (go / no-go decision table)",
    "docs\KNOWN_LIMITATIONS_PUBLIC.md      (public-facing limitations)",
    "docs\FINAL_DEMO_SCRIPT.md             (90s / 3min / 7min scripts)"
)
foreach ($d in $rcDocs) {
    $path = ($d -split "\s+")[0]
    $tag = if (Test-Path (Join-Path $repoRoot $path)) { "[found] " } else { "[MISSING]" }
    Write-Host "  $tag $d"
}
Write-Host ""

# --- User-run verification commands (printed, never executed here) -----------
Write-Host "User-run verification commands (this script does NOT run them):" -ForegroundColor Cyan
Write-Host "  # Backend tests (from the repo root; artifacts\ must be absent after)"
Write-Host "  backend\venv\Scripts\python.exe -m pytest backend\tests -q"
Write-Host ""
Write-Host "  # Frontend typecheck"
Write-Host "  cd frontend; npx tsc --noEmit"
Write-Host ""
Write-Host "  # Frontend production build (ALWAYS user-run)"
Write-Host "  cd frontend; npm run build"
Write-Host ""

# --- Tag template --------------------------------------------------------------
Write-Host "Tag command template (run manually AFTER the review commit - never by a script):" -ForegroundColor Cyan
Write-Host '  git tag v4.xx.0-short-feature-name-v1'
Write-Host '  git push origin v4.xx.0-short-feature-name-v1'
Write-Host ""
Write-Host "Reminders: fill the status table in docs\PUBLIC_RELEASE_CANDIDATE.md with real" -ForegroundColor DarkGray
Write-Host "evidence; no status is 'passed' until you ran it. Not investment advice; no live" -ForegroundColor DarkGray
Write-Host "trading; deterministic sample data." -ForegroundColor DarkGray
Write-Host ""
exit 0
