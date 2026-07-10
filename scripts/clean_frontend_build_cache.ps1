# =============================================================================
# QuantLab — Clean the Next.js build cache (Phase 39.0)
#
# Removes EXACTLY ONE folder: frontend\.next (the Next.js build cache).
# Useful when the dev server or build behaves strangely after big changes.
#
# This script NEVER: deletes anything else, touches node_modules or source,
# uses the network, or requires admin. Rebuilding the cache is your call
# (npm run dev / npm run build — user-run).
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot "frontend\.next"

# Safety: only proceed if the resolved path really ends in \frontend\.next
if ($target -notmatch '\\frontend\\\.next$') {
    Write-Host "[ERROR] Refusing: unexpected target path '$target'." -ForegroundColor Red
    exit 1
}

if (Test-Path $target) {
    Write-Host ("Removing Next.js build cache: {0}" -f $target) -ForegroundColor Yellow
    Remove-Item -Recurse -Force $target
    Write-Host "Done. It will be regenerated the next time you (yourself) run npm run dev or npm run build." -ForegroundColor Green
} else {
    Write-Host ("Nothing to do — {0} does not exist." -f $target) -ForegroundColor DarkGray
}
exit 0
