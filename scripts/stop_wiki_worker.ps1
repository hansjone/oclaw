param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "wiki_worker.pid"

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
}

Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
Write-Host "[ok] stopped pid=$procId"
