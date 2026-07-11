# =============================================================================
# QuantLab — Print the public release package summary (Phase 44.0)
#
# PRINT-ONLY. Reads local git state and prints the release-package doc paths
# and user-run commands. This script NEVER: creates tags, pushes commits,
# calls GitHub APIs, creates GitHub releases, runs builds/dev servers, runs
# tests automatically, installs packages, deletes files, deploys, or opens a
# browser.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host ""
Write-Host "=== QuantLab public release package v1 ===" -ForegroundColor Cyan
Write-Host "(public portfolio material - not a production certification)" -ForegroundColor DarkGray
Write-Host ""

$branch = git rev-parse --abbrev-ref HEAD 2>$null
$commit = git log -1 --oneline 2>$null
$latestTag = git describe --tags --abbrev=0 2>$null
Write-Host "Current branch : $branch"
Write-Host "Latest commit  : $commit"
Write-Host "Latest tag     : $latestTag"
Write-Host "Frozen tag     : v4.60.0-public-release-candidate-demo-freeze-v1 (never force-update)"
Write-Host "Release tag    : v4.61.0-browser-e2e-regression-guard-v1 (release draft targets this)"
Write-Host ""

Write-Host "Release package documents:" -ForegroundColor Cyan
$docs = @(
    "docs\GITHUB_RELEASE_DRAFT_v4.61.md       (manual copy-paste release text)",
    "docs\LINKEDIN_LAUNCH_POST.md             (post drafts + reply templates)",
    "docs\PORTFOLIO_CASE_STUDY.md             (personal-site write-up)",
    "docs\DEMO_VIDEO_SHOT_LIST.md             (recording plan + retake checks)",
    "docs\DEMO_VIDEO_90_SECOND_SCRIPT.md      (timestamped short script)",
    "docs\DEMO_VIDEO_3_MINUTE_SCRIPT.md       (timestamped long script)",
    "docs\PUBLIC_REPO_README_CHECKLIST.md     (pre-publish README checks)",
    "docs\RELEASE_ASSET_MANIFEST.md           (asset inventory + policies)"
)
foreach ($d in $docs) {
    $path = ($d -split "\s+")[0]
    $tag = if (Test-Path (Join-Path $repoRoot $path)) { "[found] " } else { "[MISSING]" }
    Write-Host "  $tag $d"
}
Write-Host ""

Write-Host "User-run verification commands (NOT run by this script):" -ForegroundColor Cyan
Write-Host "  backend\venv\Scripts\python.exe -m pytest backend\tests -q"
Write-Host "  cd frontend; npx tsc --noEmit"
Write-Host "  cd frontend; npx playwright test     # servers must already be running"
Write-Host "  cd frontend; npm run build           # user-run"
Write-Host ""
Write-Host "Reminders:" -ForegroundColor DarkGray
Write-Host "  - The GitHub Release is published MANUALLY from the draft doc; nothing here" -ForegroundColor DarkGray
Write-Host "    calls the GitHub API or creates releases/tags." -ForegroundColor DarkGray
Write-Host "  - Run the secret search in docs\SECURITY_AND_SECRETS.md before publishing." -ForegroundColor DarkGray
Write-Host "  - Frozen evidence (docs\screenshots\release_*.png) is never regenerated." -ForegroundColor DarkGray
Write-Host ""
exit 0
