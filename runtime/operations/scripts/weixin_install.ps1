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
$pluginRoot = Join-Path $env:USERPROFILE ".openclaw\\extensions\\openclaw-weixin"
function Sync-WeixinBridgeRunners {
  $bridgeSrc = Join-Path $oclawRoot "runtime\\operations\\weixin_bridge"
  foreach ($name in @("official_runner.ts", "login.ts")) {
    $srcPath = Join-Path $bridgeSrc $name
    if (-not (Test-Path $srcPath)) {
      throw "missing bridge source file: $srcPath"
    }
    Copy-Item -Path $srcPath -Destination (Join-Path $sidecarRoot $name) -Force
  }
}

New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $sidecarRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Ensure-OfficialPluginRuntimeDeps {
  if (-not (Test-Path (Join-Path $pluginRoot "package.json"))) {
    throw "official plugin root not found at $pluginRoot"
  }
  Push-Location $pluginRoot
  try {
    npm.cmd install openclaw@latest --no-save
    if ($LASTEXITCODE -ne 0) {
      throw "npm install official plugin runtime deps failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

Push-Location $sidecarRoot
try {
  if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
    npm.cmd init -y | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "npm init failed with exit code $LASTEXITCODE"
    }
  }
  npx.cmd -y @tencent-weixin/openclaw-weixin-cli@latest install
  if ($LASTEXITCODE -ne 0) {
    throw "openclaw-weixin-cli install failed with exit code $LASTEXITCODE"
  }
  npm.cmd install openclaw@latest --save tsx@4.21.0 typescript@6.0.3
  if ($LASTEXITCODE -ne 0) {
    throw "npm install bridge runtime deps failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}
Ensure-OfficialPluginRuntimeDeps
Sync-WeixinBridgeRunners
Write-Host "[ok] installed official openclaw-weixin plugin sidecar runtime into $sidecarRoot"

