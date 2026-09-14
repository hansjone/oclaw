$live = 'C:\Users\zhout\.dsh\sessions'
$bak = 'C:\Users\zhout\.dsh\upgrade-backup-20260914-074633\sessions'

Write-Output 'LIVE:'
Get-ChildItem $live -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $count = @(Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue).Count
  Write-Output ("  {0} => {1}" -f $_.Name, $count)
}

Write-Output 'BACKUP:'
Get-ChildItem $bak -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $count = @(Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue).Count
  Write-Output ("  {0} => {1}" -f $_.Name, $count)
}
