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

$venvPython = Join-Path $repoRoot "oclaw/.venv/Scripts/python.exe"
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
  & $pythonExe -m src.wiki_worker.main
  exit 0
}

$p = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "src.wiki_worker.main") -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Set-Content -Path $pidFile -Value $p.Id -Encoding ascii
Write-Host "[ok] started wiki worker pid=$($p.Id) out=$outLog err=$errLog"
