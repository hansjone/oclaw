param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [bool]$WithWikiWorker = $true,
    # Foreground: mirror merged stdout/stderr to gateway.foreground.log (same dir as start_service logs).
    [switch]$NoLogMirror = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Fail([string]$msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

$repoRoot = $null
function Resolve-RepoRoot([string]$fromDir) {
    $cur = (Resolve-Path $fromDir).Path
    for ($i = 0; $i -lt 12; $i++) {
        $cfg = Join-Path $cur "oclaw.json"
        if (Test-Path $cfg) {
            return $cur
        }
        $parent = Split-Path -Parent $cur
        if (-not $parent -or $parent -eq $cur) {
            break
        }
        $cur = $parent
    }
    return $null
}

$repoRoot = Resolve-RepoRoot $PSScriptRoot
if (-not $repoRoot) {
    # Fallback: old relative layout assumption
    $repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
}
Set-Location $repoRoot

$runDir = Join-Path $PSScriptRoot ".run"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$pidFile = Join-Path $runDir "gateway.pid"

Write-Step "Project root: $repoRoot"
Write-Step "Working directory: $repoRoot"

# Repo root must be on PYTHONPATH (top-level packages: runtime, svc, interfaces).
$env:PYTHONPATH = $repoRoot
$env:PYTHONSAFEPATH = "1"
$env:AIA_WORKSPACE_ROOT = $repoRoot
$env:OPS_WORKSPACE_ROOT = $repoRoot
$env:OCLAW_WORKSPACE = $repoRoot

$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (Test-Path $venvPython) {
    Write-Step "Using venv python: $venvPython"
    $pythonExe = $venvPython
} else {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Fail "python not found in PATH. Please install Python and retry."
    }
    Write-Step "Python detected: $($pythonCmd.Source)"
    $pythonExe = "python"
}

if (-not $SkipInstall) {
    Write-Step "Installing dependencies (pip install -r requirements.txt)"
    & $pythonExe -m pip install -r (Join-Path $repoRoot "requirements.txt")
} else {
    Write-Step "Skip dependency install"
}

. (Join-Path $PSScriptRoot "lib\ResolveRuntimeLogDir.ps1")
$logDir = Get-OclawRuntimeLogDir -RepoRoot $repoRoot
Write-Step "Runtime log dir: $logDir"
Write-Host "  (stack up / start_service: gateway.err.log + gateway.out.log here)" -ForegroundColor DarkGray
Write-Host "  (this script foreground: gateway.foreground.log when log mirror on)" -ForegroundColor DarkGray

Write-Host ""
Write-Step "Gateway URL"
Write-Host "Admin: http://$BindHost`:$Port/admin"
Write-Host "Chat:  http://$BindHost`:$Port/chat"
Write-Host "WS:    ws://$BindHost`:$Port/ws"
Write-Host ""

$configPath = Join-Path $repoRoot "oclaw.json"
if (Test-Path $configPath) {
    $env:OCLAW_CONFIG_PATH = $configPath
    Write-Step "Using OCLAW_CONFIG_PATH: $configPath"
}

if ($WithWikiWorker) {
    Write-Step "Ensuring wiki worker is running"
    & "$PSScriptRoot/start_wiki_worker.ps1" -Background
}

if ($Background) {
    Write-Step "Starting gateway in background"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $errLog = Join-Path $logDir "gateway.err.log"
    $outLog = Join-Path $logDir "gateway.out.log"
    Write-Host "stderr -> $errLog" -ForegroundColor DarkGray
    Write-Host "stdout -> $outLog" -ForegroundColor DarkGray
    $p = Start-Process -FilePath $pythonExe `
        -ArgumentList @("-m","runtime.operations","gateway","start","--host",$BindHost,"--port",$Port) `
        -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardError $errLog -RedirectStandardOutput $outLog
    Set-Content -Path $pidFile -Value "$($p.Id)" -Encoding ascii
    Write-Host "gateway.pid = $pidFile" -ForegroundColor DarkGray
    Write-Host "PID = $($p.Id)" -ForegroundColor Green
    exit 0
}

Write-Step "Starting gateway (foreground)"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
# Uvicorn writes INFO to stderr. PowerShell 7 wraps native stderr as ErrorRecord
# (red "NativeCommandError") even when non-terminating. Run under cmd.exe with
# ``2>&1`` so PS only sees a single stdout stream of plain text.
if ($BindHost -match '[&|`~]' -or $Port -lt 1 -or $Port -gt 65535) {
    Fail "Invalid -BindHost or -Port for gateway launcher."
}
$cmdLine = "cd /d `"$repoRoot`" && `"$pythonExe`" -m runtime.operations gateway start --host $BindHost --port $Port 2>&1"
if (-not $NoLogMirror) {
    $fgLog = Join-Path $logDir "gateway.foreground.log"
    Write-Host "Mirroring console to: $fgLog (pass -NoLogMirror to disable)" -ForegroundColor DarkGray
    cmd.exe /d /s /c $cmdLine | Tee-Object -FilePath $fgLog -Append
} else {
    cmd.exe /d /s /c $cmdLine
}



