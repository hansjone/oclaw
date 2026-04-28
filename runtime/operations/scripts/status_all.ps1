param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$WithoutWeixin = $false,
    [switch]$WithoutWhatsApp = $false,
    [switch]$WithWikiWorker = $false,
    [string]$WeixinChannelId = "oclaw-weixin",
    [string]$WhatsAppChannelId = "whatsapp"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Warn([string]$msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

$runDir = Join-Path $PSScriptRoot ".run"
$null = New-Item -ItemType Directory -Force -Path $runDir -ErrorAction SilentlyContinue
$gwPidFile = Join-Path $runDir "gateway.pid"
$desktopPidFile = Join-Path $runDir "desktop.pid"

Write-Step "URLs"
Write-Host "Admin: http://$BindHost`:$Port/admin"
Write-Host "Chat:  http://$BindHost`:$Port/chat"
Write-Host "WS:    ws://$BindHost`:$Port/ws"
Write-Host ""

Write-Step "PID files"
if (Test-Path $gwPidFile) {
    $gwPid = (Get-Content $gwPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    Write-Host "gateway.pid: $gwPidFile => $gwPid"
} else {
    Warn "gateway.pid not found: $gwPidFile"
}
if (Test-Path $desktopPidFile) {
    $deskPid = (Get-Content $desktopPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    Write-Host "desktop.pid: $desktopPidFile => $deskPid"
} else {
    Warn "desktop.pid not found: $desktopPidFile"
}
Write-Host ""

Write-Step "Port listener"
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Warn "No listener on port $Port"
        exit 0
    }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    Write-Host "Listening on port $Port; OwningProcess: $($pids -join ', ')"

    # Self-heal: if we have a single owning pid and no gateway.pid, write it back.
    if (-not (Test-Path $gwPidFile)) {
        $pidList = @()
        foreach ($x in @($pids)) {
            $n = 0
            if ([int]::TryParse([string]$x, [ref]$n) -and $n -gt 0) {
                $pidList += $n
            }
        }
        if ($pidList.Count -eq 1) {
            $procId = [int]$pidList[0]
            try {
                $null = Get-Process -Id $procId -ErrorAction Stop
                Set-Content -Path $gwPidFile -Value "$procId" -Encoding ascii
                Write-Host "Wrote gateway.pid => $procId" -ForegroundColor Green
            } catch {
                Warn "Cannot verify process for PID=$procId; not writing pid file."
            }
        } else {
            # Heuristic: try to pick the gateway python/uvicorn process.
            $candidates = @()
            foreach ($p in $pidList) {
                try {
                    $proc = Get-Process -Id $p -ErrorAction Stop
                    $name = [string]$proc.ProcessName
                } catch {
                    continue
                }
                $cmd = ""
                try {
                    $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction SilentlyContinue
                    if ($wmi -and $wmi.CommandLine) { $cmd = [string]$wmi.CommandLine }
                } catch {
                    $cmd = ""
                }
                if ($cmd) {
                    $low = ([string]$cmd).ToLowerInvariant()
                } else {
                    $low = ""
                }
                $score = 0
                if ($name -match "python") { $score += 2 }
                if ($low -match "uvicorn") { $score += 2 }
                if ($low -match "src\.ops") { $score += 2 }
                if ($low -match "gateway\s+start") { $score += 2 }
                if ($low -match "fastapi_app") { $score += 1 }
                $candidates += [pscustomobject]@{ Pid = [int]$p; Name = $name; Score = [int]$score; Cmd = $cmd }
            }
            $best = $candidates | Sort-Object -Property Score -Descending | Select-Object -First 1
            if ($best -and $best.Score -ge 2) {
                try {
                    $null = Get-Process -Id $best.Pid -ErrorAction Stop
                    Set-Content -Path $gwPidFile -Value "$($best.Pid)" -Encoding ascii
                    Write-Host "Wrote gateway.pid => $($best.Pid) ($($best.Name))" -ForegroundColor Green
                } catch {
                    Warn "Cannot verify process for PID=$($best.Pid); not writing pid file."
                }
            } else {
                Warn "Multiple owning processes for port $Port; cannot confidently pick gateway PID."
            }
        }
    }
} catch {
    Warn "Get-NetTCPConnection failed: $($_.Exception.Message)"
}

if (-not $WithoutWeixin) {
    Write-Host ""
    Write-Step "Weixin sidecar"
    try {
        & "$PSScriptRoot/weixin_status.ps1" -ChannelId $WeixinChannelId
    } catch {
        Warn "weixin status failed: $($_.Exception.Message)"
    }
}
if (-not $WithoutWhatsApp) {
    Write-Host ""
    Write-Step "WhatsApp sidecar"
    try {
        & "$PSScriptRoot/whatsapp_status.ps1" -ChannelId $WhatsAppChannelId
    } catch {
        Warn "whatsapp status failed: $($_.Exception.Message)"
    }
}

if ($WithWikiWorker) {
    Write-Host ""
    Write-Step "Wiki worker"
    try {
        & "$PSScriptRoot/status_wiki_worker.ps1"
    } catch {
        Warn "wiki worker status failed: $($_.Exception.Message)"
    }
}

