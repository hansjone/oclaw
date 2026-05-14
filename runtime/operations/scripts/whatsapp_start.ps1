param(
  [string]$ChannelId = "whatsapp",
  [string]$GatewayBaseUrl = "http://127.0.0.1:8787",
  [int]$GatewayWaitSeconds = 20
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..\\..\\..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$stateDir = Join-Path $sidecarRoot "state"
$sidecarPidFile = Join-Path $sidecarRoot "pid.txt"

$env:PYTHONPATH = $oclawRoot
. (Join-Path $PSScriptRoot "lib\ResolveRuntimeLogDir.ps1")
$runtimeLogDir = Get-OclawRuntimeLogDir -RepoRoot $oclawRoot

New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
New-Item -ItemType Directory -Force -Path $runtimeLogDir | Out-Null

$logPath = Join-Path $runtimeLogDir "whatsapp_sidecar.log"
$errPath = Join-Path $runtimeLogDir "whatsapp_sidecar.err.log"
$systemNodeDir = "C:\\Program Files\\nodejs"
if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
  $env:PATH = "$systemNodeDir;$env:PATH"
}

if (-not (Test-Path (Join-Path $sidecarRoot "baileys_runner.ts"))) {
  throw "whatsapp sidecar not installed. Run whatsapp_install.ps1 first."
}

$healthUrl = ($GatewayBaseUrl.TrimEnd("/") + "/health")
for ($i = 0; $i -lt $GatewayWaitSeconds; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
    if ($resp -and $resp.StatusCode -eq 200) {
      break
    }
  } catch {}
  if ($i -lt ($GatewayWaitSeconds - 1)) {
    Start-Sleep -Seconds 1
  }
}
if (-not $resp -or $resp.StatusCode -ne 200) {
  throw "oclaw gateway is not reachable at $healthUrl. Start it first: powershell -ExecutionPolicy Bypass -File .\\scripts\\start_gateway.ps1 -SkipInstall -Background"
}

$args = @(
  "/c",
  "cd /d $sidecarRoot && set OCLAW_STATE_DIR=$stateDir&& set AIA_GATEWAY_BASE_URL=$GatewayBaseUrl&& npx.cmd -y tsx baileys_runner.ts"
)
$p = Start-Process -FilePath "cmd.exe" -ArgumentList $args -WorkingDirectory $sidecarRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath
Set-Content -Path $sidecarPidFile -Value $p.Id
Write-Host "[ok] started whatsapp sidecar pid=$($p.Id) mode=baileys out=$logPath err=$errPath"
