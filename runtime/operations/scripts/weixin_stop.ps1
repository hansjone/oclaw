param(
  [string]$ChannelId = "oclaw-weixin",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$systemNodeDir = "C:\\Program Files\\nodejs"
if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
  $env:PATH = "$systemNodeDir;$env:PATH"
}

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  # runtime/operations/scripts -> repo root
  return (Resolve-Path (Join-Path $here "..\\..\\..")).Path
}

$oclawRoot = Resolve-RepoRoot
$sidecarRoot = Join-Path $oclawRoot "data\\channel_sidecar\\$ChannelId"
$pidFile = Join-Path $sidecarRoot "pid.txt"

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

function Stop-SidecarProcesses {
  param(
    [switch]$ForceKill
  )
  $procs = @(Get-SidecarProcesses | Sort-Object ProcessId -Descending)
  $oldNativePref = $PSNativeCommandUseErrorActionPreference
  try {
    $PSNativeCommandUseErrorActionPreference = $false
    foreach ($proc in $procs) {
      if ($ForceKill) {
        taskkill.exe /PID $proc.ProcessId /T /F 2>$null | Out-Null
        continue
      }
      taskkill.exe /PID $proc.ProcessId /T 2>$null | Out-Null
      if ($LASTEXITCODE -ne 0) {
        # Some process trees require force kill on Windows.
        taskkill.exe /PID $proc.ProcessId /T /F 2>$null | Out-Null
      }
    }
  } finally {
    $PSNativeCommandUseErrorActionPreference = $oldNativePref
  }
  return $procs.Count
}

if (-not (Test-Path $pidFile)) {
  $killed = Stop-SidecarProcesses -ForceKill:$Force
  if ($killed -gt 0) {
    Write-Host "[ok] cleaned stale sidecar processes count=$killed"
    exit 0
  }
  Write-Host "[ok] not running (no pid file)"
  exit 0
}

$procId = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $procId) {
  Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
  Write-Host "[ok] not running (empty pid file)"
  exit 0
}

$oldNativePref = $PSNativeCommandUseErrorActionPreference
try {
  $PSNativeCommandUseErrorActionPreference = $false
  if ($Force) {
    taskkill.exe /PID $procId /T /F 2>$null | Out-Null
  } else {
    taskkill.exe /PID $procId /T 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
      # Retry with /F to avoid noisy parent/child kill failures.
      taskkill.exe /PID $procId /T /F 2>$null | Out-Null
    }
  }
} finally {
  $PSNativeCommandUseErrorActionPreference = $oldNativePref
}

$killed = Stop-SidecarProcesses -ForceKill:$Force
Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
Write-Host "[ok] stopped pid=$procId extra_cleaned=$killed"

