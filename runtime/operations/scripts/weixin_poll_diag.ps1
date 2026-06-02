param(
  [switch]$ResetCursor = $false
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$sidecarRoot = Join-Path $repoRoot "data\channel_sidecar\oclaw-weixin"
$stateDir = Join-Path $sidecarRoot "state"
$bridgeSrc = Join-Path $repoRoot "runtime\operations\weixin_bridge\poll_diag.ts"

if (-not (Test-Path $bridgeSrc)) {
  throw "missing $bridgeSrc"
}
Copy-Item -Path $bridgeSrc -Destination (Join-Path $sidecarRoot "poll_diag.ts") -Force

$args = @("exec", "--", "tsx", "poll_diag.ts")
if ($ResetCursor) {
  $args += "--reset-cursor"
}

Push-Location $sidecarRoot
try {
  $env:OCLAW_STATE_DIR = $stateDir
  $env:OPENCLAW_STATE_DIR = $stateDir
  npm.cmd @args
} finally {
  Pop-Location
}
