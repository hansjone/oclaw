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

Push-Location $sidecarRoot
try {
  $npmRegistry = ($env:OCLAW_NPM_REGISTRY).Trim()
  $npmRegistryArgs = @()
  if ($npmRegistry) {
    $npmRegistryArgs = @("--registry", $npmRegistry)
  }
  if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
    npm.cmd init -y | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "npm init failed with exit code $LASTEXITCODE"
    }
  }
  # Pure sidecar mode:
  # - No ~/.openclaw usage
  # - Install the official plugin package into node_modules and point it to $stateDir via OPENCLAW_STATE_DIR at runtime
  npm.cmd install --no-audit --no-fund --save @tencent-weixin/openclaw-weixin@latest openclaw@latest tsx@4.21.0 typescript@6.0.3 @npmRegistryArgs
  if ($LASTEXITCODE -ne 0) {
    throw "npm install bridge runtime deps failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}
Sync-WeixinBridgeRunners
Write-Host "[ok] installed official openclaw-weixin plugin sidecar runtime into $sidecarRoot"

