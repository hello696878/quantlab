# =============================================================================
# QuantLab — Run the responsive E2E regression guard (Phase 43.0)
#
# Runs the 1440/1024/768 geometry guards against servers YOU already started.
# This script NEVER: starts servers, runs npm run dev/build or next
# dev/build, installs dependencies or browsers, deletes files, changes
# execution policy, calls external APIs, creates tags, pushes, or deploys.
# =============================================================================

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$baseUrl = if ($env:E2E_BASE_URL) { $env:E2E_BASE_URL } else { "http://localhost:3000" }

# Plain local TCP probe — no web-request cmdlets, nothing downloaded.
function Test-LocalPort([int]$port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $ok = $c.ConnectAsync("127.0.0.1", $port).Wait(3000) -and $c.Connected
        $c.Close()
        return $ok
    } catch { return $false }
}

$frontendPort = 3000
if ($baseUrl -match ":(\d+)") { $frontendPort = [int]$Matches[1] }

Write-Host "Responsive E2E guard — base URL: $baseUrl" -ForegroundColor Cyan

if (-not (Test-LocalPort 8000)) {
    Write-Host "[BLOCKED] Backend not reachable on http://localhost:8000 — start it yourself first." -ForegroundColor Red
    exit 1
}
if (-not (Test-LocalPort $frontendPort)) {
    Write-Host "[BLOCKED] Frontend not reachable at $baseUrl — start it yourself first." -ForegroundColor Red
    exit 1
}

Set-Location $frontendDir
Write-Host "Running: npx playwright test e2e/responsive.spec.ts" -ForegroundColor Cyan
npx playwright test e2e/responsive.spec.ts
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Host "Responsive guard: PASS (geometry regression signal only)." -ForegroundColor Green
} else {
    Write-Host "Responsive guard: FAIL (exit $code). Report: npm run e2e:report" -ForegroundColor Red
}
exit $code
