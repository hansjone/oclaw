param(
  [string]$ChannelId = "openclaw-weixin",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$pidFile = Join-Path $sidecarRoot "pid.txt"

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
  # Ignore if already dead.
}

Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
Write-Host "[ok] stopped pid=$procId"

