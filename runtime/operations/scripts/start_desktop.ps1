param(
    [switch]$SkipInstall = $false,
    [switch]$Background = $false,
    [switch]$KeepExistingGateway = $false
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$desktopDir = Join-Path $repoRoot "oclaw\\desktop"
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

Write-Host "==> Launching desktop app" -ForegroundColor Cyan
if ($Background) {
    # Avoid launching npm.ps1 directly (can be file-associated and open in Notepad on some setups).
    # Use hidden cmd and redirect logs to avoid black console window popup.
    $p = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c","npm.cmd","run","dev") -WorkingDirectory $desktopDir -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    Set-Content -Path $pidFile -Value "$($p.Id)" -Encoding ascii
    Write-Host "desktop.pid = $pidFile" -ForegroundColor DarkGray
    Write-Host "desktop.out = $outLog" -ForegroundColor DarkGray
    Write-Host "desktop.err = $errLog" -ForegroundColor DarkGray
    Write-Host "PID = $($p.Id)" -ForegroundColor Green
    exit 0
}
& "npm.cmd" "run" "dev"
