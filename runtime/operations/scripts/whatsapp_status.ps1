param(
  [string]$ChannelId = "whatsapp"
)

$ErrorActionPreference = "Stop"

$oclawRoot = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "..\\..\\..")).Path
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$sidecarPidFile = Join-Path $sidecarRoot "pid.txt"
if (Test-Path $sidecarPidFile) {
  $procId = (Get-Content -Path $sidecarPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
    Write-Host "status=running mode=baileys channel=$ChannelId"
    exit 0
  }
}

Write-Host "status=stopped mode=baileys channel=$ChannelId"
