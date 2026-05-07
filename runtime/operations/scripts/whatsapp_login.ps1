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

Push-Location $sidecarRoot
try {
  $env:OCLAW_STATE_DIR = $stateDir
  Write-Host "[info] whatsapp login started (foreground)."
  Write-Host "[info] If QR appears, scan it in WhatsApp -> Linked devices."
  $runnerArgs = @("-y", "tsx", "baileys_runner.ts", "--login")
  if ($VerboseRunner) {
    $runnerArgs += "--verbose"
  }
  & npx.cmd @runnerArgs
  if ($LASTEXITCODE -ne 0) {
    throw "whatsapp login runner exited with code $LASTEXITCODE"
  }
  Write-Host "[ok] whatsapp login finished"
} finally {
  Pop-Location
}
