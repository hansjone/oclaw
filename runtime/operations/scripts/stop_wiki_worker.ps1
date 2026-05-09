param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "wiki_worker.pid"

function Warn([string]$msg) {
  Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Warn-AccessHint([string]$contextMsg) {
  Warn $contextMsg
  Write-Host "      Hint: If you see 'Access is denied', re-run this terminal as Administrator." -ForegroundColor Yellow
}

if (-not (Test-Path $pidFile)) {
  Write-Host "[ok] not running (no pid file)"
  exit 0
}

$procId = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $procId) {
  Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
  Write-Host "[ok] not running (empty pid file)"
  exit 0
}

try {
  if ($Force) {
    taskkill.exe /PID $procId /T /F | Out-Null
  } else {
    taskkill.exe /PID $procId /T | Out-Null
  }
} catch {
  $msg = "$($_.Exception.Message)"
  if ($msg -match "denied|Access is denied|0x80070005|拒绝访问|拒绝") {
    Warn-AccessHint "Failed to stop wiki worker pid=$procId : $msg"
  } else {
    Warn "Failed to stop wiki worker pid=$procId : $msg"
    Write-Host "      Hint: If the process cannot be stopped due to permissions, re-run as Administrator." -ForegroundColor Yellow
  }
}

Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
Write-Host "[ok] stopped pid=$procId"
