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

if (-not (Test-Path (Join-Path $sidecarRoot "baileys_runner.ts"))) {
  throw "whatsapp sidecar not installed. Run whatsapp_install.ps1 first."
}

Push-Location $sidecarRoot
try {
  $env:OCLAW_STATE_DIR = $stateDir
  $args = @("/c", "set OCLAW_STATE_DIR=$stateDir&& npx.cmd -y tsx baileys_runner.ts --login")
  Start-Process -FilePath "cmd.exe" -ArgumentList $args -WorkingDirectory $sidecarRoot -Wait
} finally {
  Pop-Location
}
