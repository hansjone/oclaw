param(
    [int]$Port = 8787,
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Kill-ProcId([int]$procId) {
    try {
        Stop-Process -Id $procId -Force
        Write-Host "Stopped PID=$procId" -ForegroundColor Green
        return $true
    } catch {
        Warn "Failed to stop PID=$procId : $($_.Exception.Message)"
        return $false
    }
}

$runDir = Join-Path $PSScriptRoot ".run"
$pidFile = Join-Path $runDir "gateway.pid"

Write-Step "Stopping gateway"

if (Test-Path $pidFile) {
    $raw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $procId = 0
    [void][int]::TryParse([string]$raw, [ref]$procId)
    if ($procId -gt 0) {
        $ok = Kill-ProcId -procId $procId
        if ($ok) {
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            exit 0
        }
        if (-not $Force) { exit 1 }
    }
}

Write-Step "No PID file; attempting to stop by port $Port"
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Warn "No listener found on port $Port"
        exit 0
    }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        if ($p -gt 0) { [void](Kill-ProcId -procId $p) }
    }
    exit 0
} catch {
    Warn "Stop by port failed: $($_.Exception.Message)"
    if (-not $Force) { exit 1 }
}

