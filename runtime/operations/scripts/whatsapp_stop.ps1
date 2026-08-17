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

function Invoke-TaskKillQuiet {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ProcessId,
    [switch]$ForceKill
  )
  $forceArg = ""
  if ($ForceKill) { $forceArg = " /F" }
  cmd.exe /c "taskkill /PID $ProcessId /T$forceArg 1>nul 2>nul" | Out-Null
  return $LASTEXITCODE
}

if (Test-Path $sidecarPidFile) {
  $procId = (Get-Content -Path $sidecarPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($procId) {
    if ($Force) {
      [void](Invoke-TaskKillQuiet -ProcessId ([string]$procId) -ForceKill)
    } else {
      $code = Invoke-TaskKillQuiet -ProcessId ([string]$procId)
      if ($code -ne 0) {
        [void](Invoke-TaskKillQuiet -ProcessId ([string]$procId) -ForceKill)
      }
    }
  }
  Remove-Item -Force $sidecarPidFile -ErrorAction SilentlyContinue
}

# cmd.exe wrapper can leave node/tsx children; sweep leftover runners for this channel.
$needle = "channel_sidecar\$ChannelId"
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
  $_.CommandLine -and
  $_.CommandLine -like "*$needle*" -and
  $_.CommandLine -like "*baileys_runner*"
} | ForEach-Object {
  [void](Invoke-TaskKillQuiet -ProcessId ([string]$_.ProcessId) -ForceKill)
}

Write-Host "[ok] stopped whatsapp channel=$ChannelId"
