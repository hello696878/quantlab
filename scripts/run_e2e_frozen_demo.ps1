# =============================================================================
# QuantLab — Run the frozen-demo E2E regression guard (Phase 43.0)
#
# Runs the Playwright frozen-demo specs against servers YOU already started.
# This script NEVER: starts servers, runs npm run dev/build or next
# dev/build, installs dependencies or browsers, deletes files, changes
# execution policy, calls external APIs, creates tags, pushes, or deploys.
# It refuses to run when the servers are not reachable.
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

Write-Host "Frozen-demo E2E guard — base URL: $baseUrl" -ForegroundColor Cyan

if (-not (Test-LocalPort 8000)) {
    Write-Host "[BLOCKED] Backend not reachable on http://localhost:8000 — start it yourself first:" -ForegroundColor Red
    Write-Host "          cd $repoRoot\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000"
    exit 1
}
if (-not (Test-LocalPort $frontendPort)) {
    Write-Host "[BLOCKED] Frontend not reachable at $baseUrl — start it yourself first (npm run dev, or build+start for prod)." -ForegroundColor Red
    exit 1
}

Set-Location $frontendDir
Write-Host "Running: npx playwright test e2e/frozen-demo.spec.ts e2e/scenario-studio.spec.ts e2e/pairs-ko-pep.spec.ts" -ForegroundColor Cyan
npx playwright test e2e/frozen-demo.spec.ts e2e/scenario-studio.spec.ts e2e/pairs-ko-pep.spec.ts
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Host "Frozen-demo guard: PASS (regression signal only - not a certification)." -ForegroundColor Green
} else {
    Write-Host "Frozen-demo guard: FAIL (exit $code). Report: npm run e2e:report" -ForegroundColor Red
}
exit $code
