param(
  [string]$ChannelId = "whatsapp",
  [switch]$VerboseRunner
)

$ErrorActionPreference = "Stop"

$systemNodeDir = "C:\\Program Files\\nodejs"
if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
  $env:PATH = "$systemNodeDir;$env:PATH"
}

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..\\..\\..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$stateDir = Join-Path $sidecarRoot "state"

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

$stopScript = Join-Path $PSScriptRoot "whatsapp_stop.ps1"
if (Test-Path $stopScript) {
  Write-Host "[info] stopping existing sidecar so this console can print QR."
  & $stopScript -ChannelId $ChannelId -Force
}

. (Join-Path $PSScriptRoot "lib\ResolveWhatsAppProxy.ps1")
$proxyUrl = Get-OclawWhatsAppProxyUrl -StateDir $stateDir -Persist
if ($proxyUrl) {
  $env:AIA_WHATSAPP_PROXY_URL = $proxyUrl
  $env:HTTPS_PROXY = $proxyUrl
  $env:HTTP_PROXY = $proxyUrl
  Write-Host "[info] whatsapp login proxy=$proxyUrl"
}

Set-Content -Path (Join-Path $sidecarRoot "pid.txt") -Value $PID

$nodeExe = Join-Path $systemNodeDir "node.exe"
if (-not (Test-Path $nodeExe)) { $nodeExe = "node.exe" }
$tsxCli = Join-Path $sidecarRoot "node_modules\tsx\dist\cli.mjs"

Push-Location $sidecarRoot
try {
  $env:OCLAW_STATE_DIR = $stateDir
  Write-Host "[info] whatsapp login started (foreground)."
  Write-Host "[info] QR prints here if WhatsApp issues one. Background sidecar logs: data\\logs\\whatsapp_sidecar.log"
  Write-Host "[info] If QR appears, scan it in WhatsApp -> Linked devices."
  $runnerArgs = @()
  if (Test-Path $tsxCli) {
    $runnerArgs = @($tsxCli, "baileys_runner.ts", "--login")
    if ($VerboseRunner) { $runnerArgs += "--verbose" }
    & $nodeExe @runnerArgs
  } else {
    $runnerArgs = @("-y", "tsx", "baileys_runner.ts", "--login")
    if ($VerboseRunner) { $runnerArgs += "--verbose" }
    & npx.cmd @runnerArgs
  }
  if ($LASTEXITCODE -ne 0) {
    throw "whatsapp login runner exited with code $LASTEXITCODE"
  }
  Write-Host "[ok] whatsapp login finished"
} finally {
  Pop-Location
}
