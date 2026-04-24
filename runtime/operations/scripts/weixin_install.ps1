param(
  [string]$ChannelId = "oclaw-weixin",
  [string]$Package = "@tencent-weixin/oclaw-weixin@2.1.9",
  [string]$OclawRuntime = ""
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$stateDir = Join-Path $sidecarRoot "state"

New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $sidecarRoot "logs") | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

Push-Location $sidecarRoot
try {
  if (-not (Test-Path (Join-Path $sidecarRoot "package.json"))) {
    npm.cmd init -y | Out-Null
  }
  if (Test-Path (Join-Path $sidecarRoot "package-lock.json")) {
    npm.cmd ci
  } else {
    # First-time setup: install exact versions for reproducible sidecar runtime.
    if ($OclawRuntime) {
      npm.cmd install --save-exact $Package $OclawRuntime tsx@4.21.0 typescript@6.0.3
    } else {
      npm.cmd install --save-exact $Package tsx@4.21.0 typescript@6.0.3
    }
  }
  Write-Host "[ok] installed $Package into $sidecarRoot"
} finally {
  Pop-Location
}

