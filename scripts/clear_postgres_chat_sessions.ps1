$ErrorActionPreference = "Stop"
$real = Join-Path $PSScriptRoot "..\runtime\operations\scripts\clear_postgres_chat_sessions.ps1"
if (-not (Test-Path $real)) { throw "Forward target not found: $real" }
& $real @args
