param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [bool]$WithWikiWorker = $true
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Fail([string]$msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
    exit 1
}

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repoParent = Split-Path -Parent $repoRoot
Set-Location $repoParent

$runDir = Join-Path $PSScriptRoot ".run"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$pidFile = Join-Path $runDir "gateway.pid"

Write-Step "Project root: $repoRoot"
Write-Step "Working directory: $repoParent"

$env:PYTHONPATH = $repoParent

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
    $p = Start-Process -FilePath $pythonExe -ArgumentList @("-m","oclaw.runtime.operations","gateway","start","--host",$BindHost,"--port",$Port) -WorkingDirectory $repoParent -PassThru -WindowStyle Hidden
    Set-Content -Path $pidFile -Value "$($p.Id)" -Encoding ascii
    Write-Host "gateway.pid = $pidFile" -ForegroundColor DarkGray
    Write-Host "PID = $($p.Id)" -ForegroundColor Green
    exit 0
}

Write-Step "Starting gateway (foreground)"
& $pythonExe -m oclaw.runtime.operations gateway start --host $BindHost --port $Port



