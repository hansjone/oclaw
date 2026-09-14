$ErrorActionPreference = 'Stop'
$w = Get-Content 'C:\Users\zhout\.dsh\storages\workspace.json' -Raw | ConvertFrom-Json
foreach ($prop in $w.tables.workspaces.PSObject.Properties) {
  $row = $prop.Value
  Write-Output ("id={0}" -f $prop.Name)
  Write-Output ("  path={0}" -f $row.path)
  Write-Output ("  title={0}" -f $row.title)
  Write-Output ("  sessionIds={0}" -f @($row.sessionIds).Count)
}
