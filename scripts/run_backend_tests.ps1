# Runs a current-worktree snapshot in unique temporary storage. Never deletes
# repository artifacts or opens the active application database.
[CmdletBinding()]
param(
    [ValidateSet('focused', 'fast', 'full', 'profile')]
    [string]$Scope = 'full',
    [string[]]$Tests = @(),
    [string]$Python,
    [switch]$CollectOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $candidates = @(
        (Join-Path $repoRoot 'backend\venv\Scripts\python.exe'),
        (Join-Path $repoRoot '.venv\Scripts\python.exe')
    )
    $Python = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $Python) { $Python = 'python' }
}
$arguments = @((Join-Path $PSScriptRoot 'backend_test_runner.py'), '--scope', $Scope)
foreach ($test in $Tests) { $arguments += @('--test', $test) }
if ($CollectOnly) { $arguments += '--collect-only' }
& $Python @arguments
exit $LASTEXITCODE
