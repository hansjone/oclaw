# Shared: resolve the same directory as Python ``assistant_runtime_log_dir()`` / ``AIA_RUNTIME_LOG_DIR``.
function Get-OclawRuntimeLogDir {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $pythonExe = if (Test-Path $venvPython) { $venvPython } else { "python" }
    $savedPyPath = $env:PYTHONPATH
    $env:PYTHONPATH = $RepoRoot
    $dir = $null
    try {
        $dir = (& $pythonExe -c "from runtime.operations.runtime import assistant_runtime_log_dir; print(str(assistant_runtime_log_dir()))" 2>$null | Select-Object -Last 1).Trim()
    } catch { }
    if ($null -ne $savedPyPath) {
        $env:PYTHONPATH = $savedPyPath
    } else {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    if (-not $dir) {
        $dir = Join-Path $RepoRoot "data\logs"
    }
    return $dir
}
