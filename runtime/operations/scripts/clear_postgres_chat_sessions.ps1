# Wipe all chat_session rows (and related session-bound rows) on PostgreSQL only.
# Loads _local/system.env into the process, forces PG backend, sets confirmation env.
# Usage (from repo root is fine):
#   .\runtime\operations\scripts\clear_postgres_chat_sessions.ps1
# Dry-run (count only):
#   .\runtime\operations\scripts\clear_postgres_chat_sessions.ps1 -DryRun

param(
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

function Import-DotEnvFile([string]$path) {
    if (-not (Test-Path $path)) { return }
    Get-Content -LiteralPath $path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1).Trim()
        if ($k) {
            [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
        }
    }
}

$repoRoot = $null
$cur = (Resolve-Path $PSScriptRoot).Path
for ($i = 0; $i -lt 16; $i++) {
    if (Test-Path (Join-Path $cur "oclaw.json")) {
        $repoRoot = $cur
        break
    }
    $parent = Split-Path -Parent $cur
    if (-not $parent -or $parent -eq $cur) { break }
    $cur = $parent
}
if (-not $repoRoot) {
    throw "Could not find oclaw.json above $PSScriptRoot"
}
Set-Location $repoRoot
$env:PYTHONPATH = $repoRoot

$envFile = Join-Path $repoRoot "_local\system.env"
Import-DotEnvFile $envFile

$env:AIA_ASSISTANT_DB_BACKEND = "postgresql"
$env:AIA_CONFIRM_CHAT_SESSION_WIPE = "1"

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonExe = $(if (Test-Path $venvPython) { $venvPython } else { "python" })

$args = @(
    (Join-Path $repoRoot "runtime\operations\scripts\clear_all_chat_sessions.py")
)
if ($DryRun) {
    $args += "--dry-run"
} else {
    $args += "--yes"
}
$args += "--postgresql"

Write-Host "repo=$repoRoot" -ForegroundColor Cyan
Write-Host "env_file=$envFile" -ForegroundColor DarkGray
Write-Host "python=$pythonExe" -ForegroundColor DarkGray
Write-Host "dry_run=$DryRun" -ForegroundColor DarkGray

& $pythonExe @args
exit $LASTEXITCODE
