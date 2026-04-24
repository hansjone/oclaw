param(
  [string]$ChannelId = "openclaw-weixin",
  [string]$GatewayBaseUrl = "http://127.0.0.1:8787"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$stateDir = Join-Path $sidecarRoot "state"
$logDir = Join-Path $sidecarRoot "logs"
$pidFile = Join-Path $sidecarRoot "pid.txt"

if (-not (Test-Path $sidecarRoot)) {
  throw "sidecar not installed: run .\\scripts\\weixin_install.ps1 first"
}
if (-not (Test-Path (Join-Path $sidecarRoot "runner.ts"))) {
  throw "missing runner.ts (sidecar code). Re-run repo sync or restore file."
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$logPath = Join-Path $logDir "weixin_sidecar.log"
$errPath = Join-Path $logDir "weixin_sidecar.err.log"
$cmd = "cmd.exe"
$args = @(
  "/c",
  "cd /d $sidecarRoot && set OPENCLAW_STATE_DIR=$stateDir&& set AIA_GATEWAY_BASE_URL=$GatewayBaseUrl&& npm.cmd exec -- tsx runner.ts"
)

$p = Start-Process -FilePath $cmd -ArgumentList $args -WorkingDirectory $sidecarRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath
Set-Content -Path $pidFile -Value $p.Id
Write-Host "[ok] started weixin sidecar pid=$($p.Id) out=$logPath err=$errPath"

