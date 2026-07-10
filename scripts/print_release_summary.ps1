# =============================================================================
# QuantLab — Print the release summary (Phase 40.0)
#
# READ-ONLY. Prints the current branch, latest commit, version label, the
# verification commands (run by YOU), a tag command TEMPLATE, and the release
# doc paths. Uses only local git reads.
#
# This script NEVER: creates tags, commits, pushes, calls the GitHub API,
# runs npm dev/build, installs anything, fetches remote data, changes
# execution policy, deletes anything, or handles secrets.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "QuantLab — release summary (read-only; commands below are run by YOU)" -ForegroundColor Cyan
Write-Host ("Repo root: {0}" -f $repoRoot)
Write-Host ""

if ($null -eq (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[WARN] git not found on PATH — skipping branch/commit info." -ForegroundColor Yellow
} else {
    Push-Location $repoRoot
    try {
        Write-Host ("Branch:        {0}" -f (git branch --show-current)) -ForegroundColor Green
        Write-Host ("Latest commit: {0}" -f (git log -1 --oneline)) -ForegroundColor Green
        $lastTag = git describe --tags --abbrev=0 2>$null
        if ($lastTag) { Write-Host ("Latest tag:    {0}" -f $lastTag) -ForegroundColor Green }
    } finally {
        Pop-Location
    }
}
$versionFile = Join-Path $repoRoot "VERSION"
if (Test-Path $versionFile) {
    Write-Host ("Version label: {0}" -f (Get-Content $versionFile -TotalCount 1)) -ForegroundColor Green
}

Write-Host ""
Write-Host "Verification (run yourself; record real results in the release notes):" -ForegroundColor Cyan
Write-Host "  Backend tests:      cd $repoRoot; backend\venv\Scripts\python.exe -m pytest backend\tests -q"
Write-Host "  Frontend typecheck: cd $repoRoot\frontend; npx tsc --noEmit"
Write-Host "  Production build:   cd $repoRoot\frontend; npm run build      (user-run)"
Write-Host ""
Write-Host "Tag command TEMPLATE (this script never tags or pushes):" -ForegroundColor Cyan
Write-Host "  git tag v4.xx.0-short-feature-name-v1"
Write-Host "  git push origin v4.xx.0-short-feature-name-v1"
Write-Host ""
Write-Host "Release docs:" -ForegroundColor Cyan
Write-Host "  docs\RELEASE_CHECKLIST.md        (Part 1: release flow)"
Write-Host "  docs\RELEASE_NOTES_TEMPLATE.md"
Write-Host "  docs\VERSION_MANIFEST.md"
Write-Host "  CHANGELOG.md                     (move 'Unreleased' under the new version)"
Write-Host ""
Write-Host "Ground rules: milestone labels, not package publications; educational" -ForegroundColor DarkGray
Write-Host "platform — no live trading, not investment advice, not production compliance." -ForegroundColor DarkGray
exit 0
