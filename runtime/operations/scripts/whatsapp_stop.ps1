param(
  [string]$ChannelId = "whatsapp",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..\\..\\..")).Path
}

$systemNodeDir = "C:\\Program Files\\nodejs"
if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
  $env:PATH = "$systemNodeDir;$env:PATH"
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$sidecarPidFile = Join-Path $sidecarRoot "pid.txt"

if (Test-Path $sidecarPidFile) {
  $procId = (Get-Content -Path $sidecarPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($procId) {
    if ($Force) {
      taskkill.exe /PID $procId /T /F 2>$null | Out-Null
    } else {
      taskkill.exe /PID $procId /T 2>$null | Out-Null
      if ($LASTEXITCODE -ne 0) {
        taskkill.exe /PID $procId /T /F 2>$null | Out-Null
      }
    }
  }
  Remove-Item -Force $sidecarPidFile -ErrorAction SilentlyContinue
}

Write-Host "[ok] stopped whatsapp channel=$ChannelId"
