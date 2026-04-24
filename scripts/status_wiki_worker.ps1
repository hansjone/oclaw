param()

$ErrorActionPreference = "Stop"
$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "wiki_worker.pid"

if (-not (Test-Path $pidFile)) {
  Write-Host "status=stopped"
  exit 0
}

$procId = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $procId) {
  Write-Host "status=stopped"
  exit 0
}

try {
  Get-Process -Id $procId -ErrorAction Stop | Out-Null
  Write-Host "status=running pid=$procId"
} catch {
  Write-Host "status=stale_pid pid=$procId"
}
