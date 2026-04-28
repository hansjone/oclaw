param(
  [string]$ChannelId = "oclaw-weixin"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  # runtime/operations/scripts -> repo root
  return (Resolve-Path (Join-Path $here "..\\..\\..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$stateDir = Join-Path $sidecarRoot "state"

if (-not (Test-Path $sidecarRoot)) {
  New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
}

New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

Push-Location $sidecarRoot
try {
  $env:OCLAW_STATE_DIR = $stateDir
  if (Test-Path (Join-Path $sidecarRoot "login.ts")) {
    npm.cmd exec -- tsx login.ts
    exit 0
  }
  $openclawCmd = Get-Command openclaw -ErrorAction SilentlyContinue
  if (-not $openclawCmd) {
    throw "official mode requires openclaw command. Install first: npm install -g openclaw"
  }
  $systemNodeDir = "C:\\Program Files\\nodejs"
  if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
    $env:PATH = "$systemNodeDir;$env:PATH"
  }
  openclaw channels login --channel openclaw-weixin
} finally {
  Pop-Location
}

