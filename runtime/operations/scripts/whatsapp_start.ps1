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
. (Join-Path $PSScriptRoot "lib\ResolveWhatsAppProxy.ps1")
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

$bridgeSrc = Join-Path $oclawRoot "runtime\\operations\\whatsapp_bridge"
if (Test-Path $bridgeSrc) {
  foreach ($name in @("baileys_runner.ts", "auth.ts", "qr.ts", "status.ts")) {
    $srcPath = Join-Path $bridgeSrc $name
    if (Test-Path $srcPath) {
      Copy-Item -Path $srcPath -Destination (Join-Path $sidecarRoot $name) -Force
    }
  }
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

$proxyUrl = Get-OclawWhatsAppProxyUrl -StateDir $stateDir -Persist
if ($proxyUrl) {
  $env:AIA_WHATSAPP_PROXY_URL = $proxyUrl
  $env:HTTPS_PROXY = $proxyUrl
  $env:HTTP_PROXY = $proxyUrl
  Write-Host "[info] whatsapp sidecar proxy=$proxyUrl"
}

$nodeExe = Join-Path $systemNodeDir "node.exe"
if (-not (Test-Path $nodeExe)) { $nodeExe = "node.exe" }
$tsxCli = Join-Path $sidecarRoot "node_modules\tsx\dist\cli.mjs"
if (-not (Test-Path $tsxCli)) {
  throw "tsx not installed under $sidecarRoot. Run whatsapp_install.ps1 first."
}

$env:OCLAW_STATE_DIR = $stateDir
$env:AIA_GATEWAY_BASE_URL = $GatewayBaseUrl
$p = Start-Process -FilePath $nodeExe -ArgumentList @($tsxCli, "baileys_runner.ts") -WorkingDirectory $sidecarRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath
Set-Content -Path $sidecarPidFile -Value $p.Id
Write-Host "[ok] started whatsapp sidecar pid=$($p.Id) mode=baileys out=$logPath err=$errPath"
