$ErrorActionPreference = 'Stop'
$srcRoot = 'C:\Users\zhout\.dsh\upgrade-backup-20260914-074633\sessions'
$dstRoot = 'C:\Users\zhout\.dsh\sessions'

if (-not (Test-Path $srcRoot)) { throw "backup missing: $srcRoot" }
if (-not (Test-Path $dstRoot)) { New-Item -ItemType Directory -Path $dstRoot | Out-Null }

$copied = 0
$skipped = 0

Get-ChildItem $srcRoot -Directory | ForEach-Object {
  $proj = $_.Name
  $srcProj = $_.FullName
  $dstProj = Join-Path $dstRoot $proj
  if (-not (Test-Path $dstProj)) {
    New-Item -ItemType Directory -Path $dstProj | Out-Null
  }
  Get-ChildItem $srcProj -Directory | ForEach-Object {
    $sid = $_.Name
    $dstSid = Join-Path $dstProj $sid
    if (Test-Path $dstSid) {
      $skipped++
      return
    }
    Copy-Item -LiteralPath $_.FullName -Destination $dstSid -Recurse -Force
    $copied++
  }
}

Write-Output ("copied={0} skipped_existing={1}" -f $copied, $skipped)
Write-Output 'LIVE after restore:'
Get-ChildItem $dstRoot -Directory | ForEach-Object {
  $count = @(Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue).Count
  Write-Output ("  {0} => {1}" -f $_.Name, $count)
}
