param(
  [string]$ChannelId = "whatsapp"
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
$logDir = Join-Path $sidecarRoot "logs"
$bridgeSrc = Join-Path $oclawRoot "runtime\\operations\\whatsapp_bridge"

New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Push-Location $sidecarRoot
try {
  if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
    npm.cmd init -y | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "npm init failed with exit code $LASTEXITCODE" }
  }
  npm.cmd install --save @whiskeysockets/baileys@latest qrcode-terminal@latest
  if ($LASTEXITCODE -ne 0) { throw "npm install deps failed with exit code $LASTEXITCODE" }
  npm.cmd install --save https-proxy-agent@latest
  if ($LASTEXITCODE -ne 0) { throw "npm install proxy deps failed with exit code $LASTEXITCODE" }
  npm.cmd install --save tsx@latest typescript@latest
  if ($LASTEXITCODE -ne 0) { throw "npm install dev deps failed with exit code $LASTEXITCODE" }
} finally {
  Pop-Location
}

if (Test-Path $bridgeSrc) {
  foreach ($name in @("baileys_runner.ts", "auth.ts", "qr.ts")) {
    $srcPath = Join-Path $bridgeSrc $name
    if (Test-Path $srcPath) {
      Copy-Item -Path $srcPath -Destination (Join-Path $sidecarRoot $name) -Force
    }
  }
}

Write-Host "[ok] installed whatsapp baileys sidecar runtime into $sidecarRoot"
