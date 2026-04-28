param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "desktop.pid"

Write-Step "Stopping desktop app"

if (-not (Test-Path $pidFile)) {
    Warn "No PID file found: $pidFile"
    if (-not $Force) { exit 0 }
}

$raw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
$procId = 0
[void][int]::TryParse([string]$raw, [ref]$procId)
if ($procId -le 0) {
    Warn "Invalid PID in $pidFile"
    if (-not $Force) { exit 1 }
    exit 0
}

try {
    # Kill the whole process tree (cmd -> npm -> electron/node).
    # Some shells promote native command non-zero exit codes to terminating errors.
    $oldNativePref = $PSNativeCommandUseErrorActionPreference
    try {
        $PSNativeCommandUseErrorActionPreference = $false
        & taskkill /PID $procId /T /F 2>$null | Out-Null
    } finally {
        $PSNativeCommandUseErrorActionPreference = $oldNativePref
    }
    Write-Host "Stopped PID=$procId (tree)" -ForegroundColor Green
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    exit 0
} catch {
    Warn "Failed to stop PID=$procId : $($_.Exception.Message)"
    if (-not $Force) { exit 1 }
    exit 0
}

