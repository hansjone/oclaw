param()

$ErrorActionPreference = "Stop"

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "desktop.pid"
$outLog = Join-Path $runDir "desktop.out.log"
$errLog = Join-Path $runDir "desktop.err.log"

if (-not (Test-Path $pidFile)) {
    Warn "desktop.pid not found: $pidFile"
    exit 1
}

$raw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
$procId = 0
[void][int]::TryParse([string]$raw, [ref]$procId)
if ($procId -le 0) {
    Warn "Invalid PID in $pidFile"
    exit 1
}

try {
    $p = Get-Process -Id $procId -ErrorAction Stop
    Write-Host "desktop_running=1" -ForegroundColor Green
    Write-Host "pid=$procId"
    Write-Host "name=$($p.ProcessName)"
    if (Test-Path $outLog) { Write-Host "out_log=$outLog" }
    if (Test-Path $errLog) { Write-Host "err_log=$errLog" }
    exit 0
} catch {
    Warn "desktop process not found: PID=$procId"
    exit 1
}

