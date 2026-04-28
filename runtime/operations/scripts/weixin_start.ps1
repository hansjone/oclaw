param(
  [string]$ChannelId = "oclaw-weixin",
  [string]$GatewayBaseUrl = "http://127.0.0.1:8787"
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
$logDir = Join-Path $sidecarRoot "logs"
$pidFile = Join-Path $sidecarRoot "pid.txt"

function Get-SidecarProcesses {
  $escapedSidecarRoot = $sidecarRoot.Replace("\", "\\")
  $patterns = @(
    "*$ChannelId*",
    "*runner.ts*",
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
  $procs = @(Get-SidecarProcesses | Sort-Object ProcessId -Descending)
  foreach ($proc in $procs) {
    try {
      taskkill.exe /PID $proc.ProcessId /T /F | Out-Null
    } catch {
      # Best-effort cleanup; keep going if a process already exited.
    }
  }
  return $procs.Count
}

function Set-OfficialWeixinBaseUrl([string]$BaseUrl) {
  $weixinRoot = Join-Path $env:USERPROFILE ".openclaw\\openclaw-weixin"
  $accountsListPath = Join-Path $weixinRoot "accounts.json"
  if (-not (Test-Path $accountsListPath)) {
    Write-Host "[warn] official mode: accounts.json not found, skip baseUrl rewrite"
    return
  }
  $ids = @()
  try {
    $parsed = Get-Content -Path $accountsListPath -Raw | ConvertFrom-Json
    if ($parsed -is [System.Array]) {
      $ids = @($parsed)
    }
  } catch {
    Write-Host "[warn] official mode: failed to parse accounts.json"
    return
  }
  foreach ($aid in $ids) {
    $idText = [string]$aid
    if (-not $idText) { continue }
    $accPath = Join-Path (Join-Path $weixinRoot "accounts") "$idText.json"
    if (-not (Test-Path $accPath)) { continue }
    try {
      $obj = Get-Content -Path $accPath -Raw | ConvertFrom-Json
      $obj.baseUrl = $BaseUrl
      $json = $obj | ConvertTo-Json -Depth 8
      $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
      [System.IO.File]::WriteAllText($accPath, $json + "`n", $utf8NoBom)
      Write-Host "[ok] official mode: set baseUrl for $idText -> $BaseUrl"
    } catch {
      Write-Host "[warn] official mode: failed to rewrite $accPath"
    }
  }
}

if (-not (Test-Path $sidecarRoot)) {
  New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$cleaned = Stop-SidecarProcesses
Remove-Item -Force $pidFile -ErrorAction SilentlyContinue

$logPath = Join-Path $logDir "weixin_sidecar.log"
$errPath = Join-Path $logDir "weixin_sidecar.err.log"
if (Test-Path (Join-Path $sidecarRoot "runner.ts")) {
  $cmd = "cmd.exe"
  $args = @(
    "/c",
    "cd /d $sidecarRoot && set OCLAW_STATE_DIR=$stateDir&& set AIA_GATEWAY_BASE_URL=$GatewayBaseUrl&& npm.cmd exec -- tsx runner.ts"
  )
  $p = Start-Process -FilePath $cmd -ArgumentList $args -WorkingDirectory $sidecarRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath
  Set-Content -Path $pidFile -Value $p.Id
  Write-Host "[ok] started weixin sidecar pid=$($p.Id) cleaned=$cleaned out=$logPath err=$errPath"
  exit 0
}

$openclawCmd = Get-Command openclaw -ErrorAction SilentlyContinue
if (-not $openclawCmd) {
  throw "official mode requires openclaw command. Install first: npm install -g openclaw"
}
# Ensure OpenClaw runs on the real Node.js runtime (includes npm layout).
$systemNodeDir = "C:\\Program Files\\nodejs"
if (Test-Path (Join-Path $systemNodeDir "node.exe")) {
  $env:PATH = "$systemNodeDir;$env:PATH"
}
Set-OfficialWeixinBaseUrl -BaseUrl $GatewayBaseUrl
$args = @("/c", "openclaw gateway --allow-unconfigured")
$p = Start-Process -FilePath "cmd.exe" -ArgumentList $args -WorkingDirectory $oclawRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath
Set-Content -Path $pidFile -Value $p.Id
Write-Host "[ok] started openclaw gateway bridge pid=$($p.Id) cleaned=$cleaned out=$logPath err=$errPath"

