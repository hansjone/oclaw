param(
  [string]$ChannelId = "openclaw-weixin"
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
  Write-Host "status=stopped"
  exit 0
}

$procId = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $procId) {
  Write-Host "status=stopped"
  exit 0
}

$exists = $false
try {
  Get-Process -Id $procId -ErrorAction Stop | Out-Null
  $exists = $true
} catch {}

if ($exists) {
  Write-Host "status=running pid=$procId"
} else {
  Write-Host "status=stale_pid pid=$procId"
}

