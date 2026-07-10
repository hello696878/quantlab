# =============================================================================
# QuantLab — Repository Hygiene Check (Phase 41.0)
#
# READ-ONLY. Prints the git state and whether the usual local-only folders/
# files exist (so you can see at a glance what must never be committed).
#
# This script NEVER: deletes or changes files, installs packages, calls
# external APIs, pushes, tags, changes execution policy, runs npm dev/build,
# or handles secrets. It only reads. See docs/REPOSITORY_HYGIENE.md.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "QuantLab Repository Hygiene Check (read-only)" -ForegroundColor Cyan
Write-Host ("Repo root: {0}" -f $repoRoot)
Write-Host ""

if ($null -eq (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[WARN] git not found on PATH — skipping git info." -ForegroundColor Yellow
} else {
    Push-Location $repoRoot
    try {
        Write-Host ("Branch:        {0}" -f (git branch --show-current)) -ForegroundColor Green
        Write-Host ("Latest commit: {0}" -f (git log -1 --oneline)) -ForegroundColor Green
        Write-Host ""
        Write-Host "git status --short:" -ForegroundColor Cyan
        $status = git status --short
        if ($status) { $status | ForEach-Object { Write-Host ("  {0}" -f $_) } }
        else { Write-Host "  (clean working tree)" -ForegroundColor DarkGray }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Local-only paths (present = fine locally; must never be committed):" -ForegroundColor Cyan
$checks = @(
    @{ Path = ".env";                 Label = ".env file (root)" },
    @{ Path = "frontend\.env.local";  Label = "frontend\.env.local" },
    @{ Path = ".venv";                Label = ".venv (alternate venv)" },
    @{ Path = "backend\venv";         Label = "backend\venv (repo venv)" },
    @{ Path = "frontend\.next";       Label = "frontend\.next (build cache)" },
    @{ Path = "artifacts";            Label = "artifacts (should also be absent after test runs)" },
    @{ Path = "frontend\node_modules"; Label = "frontend\node_modules" }
)
foreach ($c in $checks) {
    $exists = Test-Path (Join-Path $repoRoot $c.Path)
    $tag = if ($exists) { "[exists]" } else { "[absent]" }
    Write-Host ("  {0,-9} {1}" -f $tag, $c.Label) -ForegroundColor $(if ($exists) { "Yellow" } else { "DarkGray" })
}

Write-Host ""
Write-Host "Reminders:" -ForegroundColor Cyan
Write-Host "  - Never commit secrets/keys; the repo needs none (docs\SECURITY_AND_SECRETS.md)."
Write-Host "  - Inspect 'git diff --cached' before every commit (docs\REPOSITORY_HYGIENE.md)."
Write-Host "  - Release flow: docs\RELEASE_CHECKLIST.md (Part 1); versioning: docs\VERSION_MANIFEST.md."
Write-Host ""
Write-Host "Read-only: nothing was changed, deleted, installed, or contacted." -ForegroundColor DarkGray
exit 0
