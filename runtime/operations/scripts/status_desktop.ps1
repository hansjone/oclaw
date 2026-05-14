param()

$ErrorActionPreference = "Stop"

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$env:PYTHONPATH = $repoRoot
. (Join-Path $PSScriptRoot "lib\ResolveRuntimeLogDir.ps1")
$logDir = Get-OclawRuntimeLogDir -RepoRoot $repoRoot

$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "desktop.pid"
$desktopLog = Join-Path $logDir "desktop.log"
$backendLog = Join-Path $logDir "backend.log"
$channelWecomLog = Join-Path $logDir "channel-wecom.log"

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
    if (Test-Path $desktopLog) { Write-Host "desktop_log=$desktopLog" }
    if (Test-Path $backendLog) { Write-Host "backend_log=$backendLog" }
    if (Test-Path $channelWecomLog) { Write-Host "channel_wecom_log=$channelWecomLog" }
    exit 0
} catch {
    Warn "desktop process not found: PID=$procId"
    exit 1
}

