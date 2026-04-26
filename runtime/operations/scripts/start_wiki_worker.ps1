param(
  [switch]$Background = $true
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  $here = Split-Path -Parent $PSCommandPath
  return (Resolve-Path (Join-Path $here "..")).Path
}

$repoRoot = Resolve-RepoRoot
$runDir = Join-Path $PSScriptRoot ".run"
$null = New-Item -ItemType Directory -Force -Path $runDir -ErrorAction SilentlyContinue
$pidFile = Join-Path $runDir "wiki_worker.pid"
$outLog = Join-Path $runDir "wiki_worker.out.log"
$errLog = Join-Path $runDir "wiki_worker.err.log"

function Test-AlivePid([int]$procId) {
  try {
    $p = Get-Process -Id $procId -ErrorAction Stop
    return $null -ne $p
  } catch {
    return $false
  }
}

$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (Test-Path $venvPython) {
  $pythonExe = $venvPython
} else {
  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCmd) {
    throw "python not found in PATH"
  }
  $pythonExe = "python"
}

if (-not $Background) {
  & $pythonExe -m oclaw.runtime.workers.wiki.main
  exit 0
}

if (Test-Path $pidFile) {
  $raw = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  $existing = 0
  [void][int]::TryParse([string]$raw, [ref]$existing)
  if ($existing -gt 0 -and (Test-AlivePid $existing)) {
    Write-Host "[ok] wiki worker already running pid=$existing"
    exit 0
  }
}

$p = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "oclaw.runtime.workers.wiki.main") -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Set-Content -Path $pidFile -Value $p.Id -Encoding ascii
Write-Host "[ok] started wiki worker pid=$($p.Id) out=$outLog err=$errLog"

