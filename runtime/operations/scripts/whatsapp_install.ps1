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
$bridgeSrc = Join-Path $oclawRoot "runtime\\operations\\whatsapp_bridge"

# Pin known-good versions to avoid breakage from upstream latest releases.
$baileysVersion = "7.0.0-rc.9"
$qrcodeVersion = "0.12.0"
$httpsProxyAgentVersion = "7.0.6"
$tsxVersion = "4.20.3"
$typescriptVersion = "5.8.2"

New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

Push-Location $sidecarRoot
try {
  if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
    npm.cmd init -y | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "npm init failed with exit code $LASTEXITCODE" }
  }
  # Remove problematic package when present (seen on some environments with latest dependency graph).
  npm.cmd remove whatsapp-rust-bridge | Out-Null

  npm.cmd install --save --save-exact @whiskeysockets/baileys@$baileysVersion qrcode-terminal@$qrcodeVersion
  if ($LASTEXITCODE -ne 0) { throw "npm install deps failed with exit code $LASTEXITCODE" }
  npm.cmd install --save --save-exact https-proxy-agent@$httpsProxyAgentVersion
  if ($LASTEXITCODE -ne 0) { throw "npm install proxy deps failed with exit code $LASTEXITCODE" }
  npm.cmd install --save --save-exact tsx@$tsxVersion typescript@$typescriptVersion
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
