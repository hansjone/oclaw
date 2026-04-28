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
$pidFile = Join-Path $sidecarRoot "pid.txt"
$systemNodeDir = "C:\\Program Files\\nodejs"
if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
  $env:PATH = "$systemNodeDir;$env:PATH"
}

function Get-SidecarProcesses {
  $escapedSidecarRoot = $sidecarRoot.Replace("\", "\\")
  $patterns = @(
    "*$ChannelId*",
    "*runner.ts*",
    "*official_runner.ts*",
    "*$escapedSidecarRoot*"
  )
  Get-CimInstance Win32_Process | Where-Object {
    $cmd = [string]($_.CommandLine)
    if (-not $cmd) { return $false }
    foreach ($pattern in $patterns) {
      if ($cmd -like $pattern) { return $true }
    }
    return $false
  }
}

if (-not (Test-Path $pidFile)) {
  $sidecarProcs = @(Get-SidecarProcesses)
  if ($sidecarProcs.Count -gt 0) {
    $pids = ($sidecarProcs | Select-Object -ExpandProperty ProcessId) -join ","
    Write-Host "status=orphaned count=$($sidecarProcs.Count) pids=$pids"
    exit 0
  }
  Write-Host "status=stopped"
  exit 0
}

$procId = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $procId) {
  Write-Host "status=stopped"
  exit 0
}

$exists = $false
try {
  Get-Process -Id $procId -ErrorAction Stop | Out-Null
  $exists = $true
} catch {}

if ($exists) {
  $sidecarProcs = @(Get-SidecarProcesses)
  Write-Host "status=running pid=$procId matches=$($sidecarProcs.Count)"
} else {
  $sidecarProcs = @(Get-SidecarProcesses)
  if ($sidecarProcs.Count -gt 0) {
    $pids = ($sidecarProcs | Select-Object -ExpandProperty ProcessId) -join ","
    Write-Host "status=orphaned stale_pid=$procId count=$($sidecarProcs.Count) pids=$pids"
    exit 0
  }
  Write-Host "status=stale_pid pid=$procId"
}

