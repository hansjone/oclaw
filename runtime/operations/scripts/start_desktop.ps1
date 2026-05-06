param(
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [switch]$KeepExistingGateway = $false,
    [string]$GatewayBaseUrl = "",
    [bool]$WithWikiWorker = $true
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$repoParent = Split-Path -Parent $repoRoot
$desktopDir = Join-Path $repoRoot "desktop"
$runDir = Join-Path $PSScriptRoot ".run"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$pidFile = Join-Path $runDir "desktop.pid"
$outLog = Join-Path $runDir "desktop.out.log"
$errLog = Join-Path $runDir "desktop.err.log"

if (-not (Test-Path $desktopDir)) {
    Write-Host "[ERROR] desktop directory not found: $desktopDir" -ForegroundColor Red
    exit 1
}

Set-Location $desktopDir
$env:PYTHONPATH = $repoParent
$env:PYTHONSAFEPATH = "1"
$env:AIA_WORKSPACE_ROOT = $repoRoot
$env:OPS_WORKSPACE_ROOT = $repoRoot
$env:OCLAW_WORKSPACE = $repoRoot

# Do not inherit attach-mode env from a parent shell when launching standalone desktop.
Remove-Item Env:OCLAW_DESKTOP_EMBED_BACKEND -ErrorAction SilentlyContinue
Remove-Item Env:OCLAW_DESKTOP_GATEWAY_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:OCLAW_DESKTOP_SKIP_CHANNEL -ErrorAction SilentlyContinue

if ($KeepExistingGateway) {
    $gw = if ($GatewayBaseUrl) { $GatewayBaseUrl.Trim() } else { "http://127.0.0.1:8787" }
    $env:OCLAW_DESKTOP_EMBED_BACKEND = "0"
    $env:OCLAW_DESKTOP_GATEWAY_BASE_URL = $gw
    $env:OCLAW_DESKTOP_SKIP_CHANNEL = "1"
    Write-Host "==> Desktop will use existing gateway (no second listener): $gw" -ForegroundColor Cyan
}

if (-not $KeepExistingGateway) {
    Write-Host "==> Cleaning previous gateway listener" -ForegroundColor Cyan
    try {
        & "$PSScriptRoot/stop_gateway.ps1" -Force
    } catch {
        Write-Host "[WARN] Failed to pre-stop gateway: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if (-not $SkipInstall) {
    Write-Host "==> Installing desktop dependencies" -ForegroundColor Cyan
    npm install
}

if ($WithWikiWorker) {
    Write-Host "==> Ensuring wiki worker is running" -ForegroundColor Cyan
    & "$PSScriptRoot/start_wiki_worker.ps1" -Background
}

Write-Host "==> Launching desktop app" -ForegroundColor Cyan
if ($Background) {
    # Do NOT redirect stdout/stderr here: on Windows, piping npm/electron stdio can prevent the GUI from showing.
    # Prefer the Electron shim directly; fallback to npm run dev (still without redirects).
    $electronCmd = Join-Path $desktopDir "node_modules\.bin\electron.cmd"
    $p = $null
    if (Test-Path $electronCmd) {
        $p = Start-Process -FilePath $electronCmd -ArgumentList @(".") -WorkingDirectory $desktopDir -PassThru -WindowStyle Hidden
    }
    if (-not $p) {
        $p = Start-Process -FilePath "npm.cmd" -ArgumentList @("run","dev") -WorkingDirectory $desktopDir -PassThru -WindowStyle Hidden
    }
    Set-Content -Path $pidFile -Value "$($p.Id)" -Encoding ascii
    Write-Host "desktop.pid = $pidFile" -ForegroundColor DarkGray
    Write-Host "Embedded backend/chat logs (Electron): see %APPDATA%\oclaw\logs\desktop.log / backend.log" -ForegroundColor DarkGray
    Write-Host "PID = $($p.Id)" -ForegroundColor Green
    Write-Host "==> Desktop launched in background (this script exits now)." -ForegroundColor Cyan
    exit 0
}
& "npm.cmd" "run" "dev"


