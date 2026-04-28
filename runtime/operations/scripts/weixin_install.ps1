param(
  [string]$ChannelId = "oclaw-weixin",
  [string]$LocalSourcePath = "",
  [switch]$UseOpenclawCli = $false
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

if ($UseOpenclawCli) {
  # Do not require a globally-installed openclaw CLI.
  # We install openclaw into the sidecar runtime and put node_modules/.bin on PATH
  # so the official installer can run `openclaw ...` commands.
  Push-Location $sidecarRoot
  try {
    if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
      npm.cmd init -y | Out-Null
      if ($LASTEXITCODE -ne 0) {
        throw "npm init failed with exit code $LASTEXITCODE"
      }
    }
    npm.cmd install openclaw@latest --save
    if ($LASTEXITCODE -ne 0) {
      throw "npm install openclaw failed with exit code $LASTEXITCODE"
    }
    $env:PATH = (Join-Path $sidecarRoot "node_modules\\.bin") + ";" + $env:PATH
    npx.cmd -y @tencent-weixin/openclaw-weixin-cli@latest install
    if ($LASTEXITCODE -ne 0) {
      throw "openclaw-weixin-cli install failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
  Ensure-OfficialPluginRuntimeDeps
  Push-Location $sidecarRoot
  try {
    npm.cmd install openclaw@latest --save tsx@4.21.0 typescript@6.0.3
    if ($LASTEXITCODE -ne 0) {
      throw "npm install bridge runtime deps failed with exit code $LASTEXITCODE"
    }
    $bridgeSrc = Join-Path $oclawRoot "runtime\\operations\\weixin_bridge"
    Copy-Item -Path (Join-Path $bridgeSrc "runner.ts") -Destination (Join-Path $sidecarRoot "runner.ts") -Force
    Copy-Item -Path (Join-Path $bridgeSrc "official_runner.ts") -Destination (Join-Path $sidecarRoot "official_runner.ts") -Force
    Copy-Item -Path (Join-Path $bridgeSrc "login.ts") -Destination (Join-Path $sidecarRoot "login.ts") -Force
  } finally {
    Pop-Location
  }
  Write-Host "[ok] installed official openclaw-weixin plugin + native/fallback sidecar runtime"
  exit 0
}

if (-not $LocalSourcePath) {
  throw "LocalSourcePath is required in sidecar mode. Example: .\\scripts\\weixin_install.ps1 -LocalSourcePath D:\\path\\to\\your-weixin-module"
}

Push-Location $sidecarRoot
try {
  if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
    npm.cmd init -y | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "npm init failed with exit code $LASTEXITCODE"
    }
  }

  $src = (Resolve-Path $LocalSourcePath).Path
  npm.cmd install --save-exact $src tsx@4.21.0 typescript@6.0.3
  if ($LASTEXITCODE -ne 0) {
    throw "npm install local source failed with exit code $LASTEXITCODE"
  }

  if (-not (Test-Path (Join-Path $sidecarRoot "runner.ts"))) {
    throw "install completed but runner.ts is missing (invalid sidecar package/source)"
  }
  if (-not (Test-Path (Join-Path $sidecarRoot "login.ts"))) {
    throw "install completed but login.ts is missing (invalid sidecar package/source)"
  }
  Write-Host "[ok] installed local weixin sidecar into $sidecarRoot"
} finally {
  Pop-Location
}

