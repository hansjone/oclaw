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
$bridgeSrc = Join-Path $oclawRoot "runtime\\operations\\weixin_bridge"
$pluginRoot = Join-Path $env:USERPROFILE ".openclaw\\extensions\\openclaw-weixin"
$runnerMode = [string]($env:AIA_WEIXIN_RUNNER_MODE)
if (-not $runnerMode) { $runnerMode = "official" }
$runnerMode = $runnerMode.Trim().ToLowerInvariant()

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
  $procs = @(Get-SidecarProcesses | Sort-Object ProcessId -Descending)
  $oldNativePref = $PSNativeCommandUseErrorActionPreference
  try {
    $PSNativeCommandUseErrorActionPreference = $false
    foreach ($proc in $procs) {
      taskkill.exe /PID $proc.ProcessId /T /F 2>$null | Out-Null
    }
  } finally {
    $PSNativeCommandUseErrorActionPreference = $oldNativePref
  }
  return $procs.Count
}

function Ensure-OfficialPluginRuntimeDeps {
  if (-not (Test-Path (Join-Path $pluginRoot "package.json"))) {
    throw "official plugin root not found at $pluginRoot"
  }
  if (Test-Path (Join-Path $pluginRoot "node_modules\\openclaw\\package.json")) {
    return
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

if (-not (Test-Path $sidecarRoot)) {
  New-Item -ItemType Directory -Force -Path $sidecarRoot | Out-Null
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

$cleaned = Stop-SidecarProcesses
Remove-Item -Force $pidFile -ErrorAction SilentlyContinue

if (Test-Path $bridgeSrc) {
  foreach ($name in @("runner.ts", "official_runner.ts", "login.ts")) {
    $srcPath = Join-Path $bridgeSrc $name
    if (Test-Path $srcPath) {
      Copy-Item -Path $srcPath -Destination (Join-Path $sidecarRoot $name) -Force
    }
  }
}

$logPath = Join-Path $logDir "weixin_sidecar.log"
$errPath = Join-Path $logDir "weixin_sidecar.err.log"
if ((Test-Path (Join-Path $sidecarRoot "runner.ts")) -or (Test-Path (Join-Path $sidecarRoot "official_runner.ts"))) {
  $runnerFile = "official_runner.ts"
  if ($runnerMode -eq "legacy") {
    $runnerFile = "runner.ts"
  }
  if ($runnerMode -eq "official") {
    Ensure-OfficialPluginRuntimeDeps
  }
  if (-not (Test-Path (Join-Path $sidecarRoot $runnerFile))) {
    throw "selected runner file missing: $runnerFile"
  }
  $cmd = "cmd.exe"
  $args = @(
    "/c",
    "cd /d $sidecarRoot && set OCLAW_STATE_DIR=$stateDir&& set AIA_GATEWAY_BASE_URL=$GatewayBaseUrl&& set NODE_PATH=$sidecarRoot\node_modules&& npm.cmd exec -- tsx $runnerFile"
  )
  $p = Start-Process -FilePath $cmd -ArgumentList $args -WorkingDirectory $sidecarRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $logPath -RedirectStandardError $errPath
  Set-Content -Path $pidFile -Value $p.Id
  Write-Host "[ok] started weixin sidecar pid=$($p.Id) mode=$runnerMode cleaned=$cleaned out=$logPath err=$errPath"
  exit 0
}

throw "No runner.ts/official_runner.ts found in sidecar root. Re-run weixin_install.ps1 -UseOpenclawCli."

