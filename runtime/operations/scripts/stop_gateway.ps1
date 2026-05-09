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

function Warn-AccessHint([string]$contextMsg) {
    Warn $contextMsg
    Write-Host "      Hint: If you see 'Access is denied', re-run this terminal as Administrator." -ForegroundColor Yellow
}

function Kill-ProcId([int]$procId, [bool]$forceKill) {
    $exists = $null
    try {
        $exists = Get-Process -Id $procId -ErrorAction SilentlyContinue
    } catch {
        $exists = $null
    }
    if (-not $exists) {
        Write-Host "PID=$procId already exited" -ForegroundColor DarkGray
        return $true
    }
    try {
        Stop-Process -Id $procId -Force:$forceKill
        Write-Host "Stopped PID=$procId" -ForegroundColor Green
        return $true
    } catch {
        $ex = $_.Exception
        $msg = "$($ex.Message)"
        $hresult = $null
        try { $hresult = $ex.HResult } catch { $hresult = $null }
        $isAccessDenied = $false
        if ($msg -match "denied|Access is denied|0x80070005") { $isAccessDenied = $true }
        if ($hresult -eq -2147024891) { $isAccessDenied = $true } # 0x80070005 Access is denied

        if ($isAccessDenied) {
            Warn-AccessHint "Failed to stop PID=$procId : $msg"
        } else {
            Warn "Failed to stop PID=$procId : $msg"
            Write-Host "      Hint: If the process cannot be stopped due to permissions, re-run as Administrator." -ForegroundColor Yellow
        }
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
        Write-Step "Attempting to stop by PID file: $pidFile (PID=$procId)"
        $ok = Kill-ProcId -procId $procId -forceKill ([bool]$Force)
        if ($ok) {
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            # Keep going to also clean up any orphan listeners on $Port.
        } else {
            # Stale pid file is common after crashes; fall back to stop-by-port.
            if ($Force) {
                Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            } else {
                Warn "PID file kill failed; falling back to stop-by-port. Re-run with -Force to also clear pid file."
            }
        }
    }
}

Write-Step "Attempting to stop by port $Port"
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Warn "No listener found on port $Port"
        exit 0
    }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($p in $pids) {
        if ($p -gt 0) { [void](Kill-ProcId -procId $p -forceKill ([bool]$Force)) }
    }
    exit 0
} catch {
    $ex = $_.Exception
    $msg = "$($ex.Message)"
    $hresult = $null
    try { $hresult = $ex.HResult } catch { $hresult = $null }
    $isAccessDenied = $false
    if ($msg -match "denied|Access is denied|0x80070005") { $isAccessDenied = $true }
    if ($hresult -eq -2147024891) { $isAccessDenied = $true } # 0x80070005 Access is denied

    if ($isAccessDenied) {
        Warn-AccessHint "Stop by port failed: $msg"
    } else {
        Warn "Stop by port failed: $msg"
        Write-Host "      Hint: If the listener cannot be stopped due to permissions, re-run as Administrator." -ForegroundColor Yellow
    }
    if (-not $Force) { exit 1 }
}

