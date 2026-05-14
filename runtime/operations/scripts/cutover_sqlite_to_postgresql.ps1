<#
.SYNOPSIS
  Backup assistant SQLite DB, optionally dry-run, then import into PostgreSQL (empty schema).

.DESCRIPTION
  1) Resolves SQLite path (explicit -SqlitePath or via Python db_path() / AIA_ASSISTANT_DB_PATH).
  2) Copies the file to data/pg_cutover_backups/ (or -BackupDir).
  3) Runs migrate_assistant_sqlite_to_postgresql.py --dry-run unless -SkipDryRun.
  4) Runs the same script without --dry-run unless -DryRunOnly.

  Set -PgUrl and/or ensure AIA_ASSISTANT_DATABASE_URL is set; with -LoadSystemEnv, URL may come only from _local/system.env (then -PgUrl can be omitted).

.EXAMPLE
  .\cutover_sqlite_to_postgresql.ps1 -PgUrl "postgresql+psycopg://postgres:PASS@127.0.0.1:5432/oclaw"

.EXAMPLE
  $env:AIA_ASSISTANT_DATABASE_URL = "postgresql+psycopg://..."
  .\cutover_sqlite_to_postgresql.ps1

.EXAMPLE
  .\cutover_sqlite_to_postgresql.ps1 -SqlitePath "D:\data\ai_ops.sqlite" -PgUrl "postgresql://..." -DryRunOnly
#>
[CmdletBinding()]
param(
    [string] $PgUrl = "",
    [string] $SqlitePath = "",
    [string] $BackupDir = "",
    [switch] $LoadSystemEnv,
    [switch] $SkipDryRun,
    [switch] $DryRunOnly,
    [switch] $NoBackup
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot

if ($LoadSystemEnv) {
    $envFile = Join-Path $RepoRoot "_local\system.env"
    if (Test-Path -LiteralPath $envFile) {
        Get-Content -LiteralPath $envFile | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#")) { return }
            $i = $line.IndexOf("=")
            if ($i -lt 1) { return }
            $k = $line.Substring(0, $i).Trim()
            $v = $line.Substring($i + 1).Trim()
            if ($k) { Set-Item -Path "Env:$k" -Value $v }
        }
        Write-Host "Loaded _local/system.env into process environment."
    }
    else {
        Write-Warning "LoadSystemEnv specified but $envFile not found."
    }
}

if (-not $PgUrl) {
    $PgUrl = $env:AIA_ASSISTANT_DATABASE_URL
}
if (-not $PgUrl -and -not $LoadSystemEnv) {
    throw "Provide -PgUrl, set AIA_ASSISTANT_DATABASE_URL, or use -LoadSystemEnv (PostgreSQL URL in _local/system.env)."
}

if (-not $SqlitePath) {
    $env:_OC_REPO_ROOT_FOR_PY = $RepoRoot
    try {
        $SqlitePath = (& python -c "import os,sys; sys.path.insert(0, os.environ['_OC_REPO_ROOT_FOR_PY']); from svc.config.paths import db_path; print(db_path(), end='')").Trim()
    }
    finally {
        Remove-Item Env:_OC_REPO_ROOT_FOR_PY -ErrorAction SilentlyContinue
    }
    if (-not $SqlitePath) { throw "Could not resolve SQLite path via db_path()." }
    Write-Host "Resolved SQLite: $SqlitePath"
}

if (-not (Test-Path -LiteralPath $SqlitePath)) {
    throw "SQLite file not found: $SqlitePath"
}

$resolvedSqlite = (Resolve-Path -LiteralPath $SqlitePath).Path
$migrate = Join-Path $RepoRoot "runtime\operations\scripts\migrate_assistant_sqlite_to_postgresql.py"
if (-not (Test-Path -LiteralPath $migrate)) {
    throw "Migration script not found: $migrate"
}

if (-not $BackupDir) {
    $BackupDir = Join-Path $RepoRoot "data\pg_cutover_backups"
}
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$leaf = [System.IO.Path]::GetFileNameWithoutExtension($resolvedSqlite)
$bakName = "${leaf}_pre_pg_${stamp}.sqlite"
$bakPath = Join-Path $BackupDir $bakName

if (-not $NoBackup) {
    Copy-Item -LiteralPath $resolvedSqlite -Destination $bakPath -Force
    Write-Host "Backup written: $bakPath"
}
else {
    Write-Warning "NoBackup: skipping file copy (no SQLite backup created)."
}

$common = @($migrate)
if ($LoadSystemEnv) {
    $common += "--load-system-env"
}
$common += "--sqlite", $resolvedSqlite
if ($PgUrl) {
    $common += @("--pg-url", $PgUrl)
}

if (-not $SkipDryRun) {
    Write-Host "=== Dry-run (row counts, no PG writes) ===" -ForegroundColor Cyan
    & python @common "--dry-run"
    if ($LASTEXITCODE -ne 0) { throw "Dry-run failed (exit $LASTEXITCODE)." }
}

if ($DryRunOnly) {
    Write-Host "DryRunOnly: skipping live import." -ForegroundColor Yellow
    exit 0
}

Write-Host "=== Live import into PostgreSQL ===" -ForegroundColor Cyan
& python @common
if ($LASTEXITCODE -ne 0) { throw "Migration failed (exit $LASTEXITCODE)." }

Write-Host ""
Write-Host "Done. Next: set AIA_ASSISTANT_DB_BACKEND=postgresql and AIA_ASSISTANT_DATABASE_URL in deployment, restart gateway." -ForegroundColor Green
