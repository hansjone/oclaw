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
$stateDir = Join-Path $sidecarRoot "state"

if (-not (Test-Path $sidecarRoot)) {
  throw "sidecar not installed: run .\\scripts\\weixin_install.ps1 first"
}

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

Push-Location $sidecarRoot
try {
  $env:OPENCLAW_STATE_DIR = $stateDir
  if (-not (Test-Path (Join-Path $sidecarRoot "login.ts"))) {
    throw "missing login.ts"
  }
  npm.cmd exec -- tsx login.ts
} finally {
  Pop-Location
}

