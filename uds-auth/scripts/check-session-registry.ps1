$ErrorActionPreference = 'Stop'
$w = Get-Content 'C:\Users\zhout\.dsh\storages\workspace.json' -Raw | ConvertFrom-Json
$archived = [System.Collections.Generic.HashSet[string]]::new([string[]]@($w.global.archivedSessionIds))
Write-Output ("archived count=" + $archived.Count)

$liveIds = New-Object System.Collections.Generic.List[string]
Get-ChildItem 'C:\Users\zhout\.dsh\sessions' -Directory | ForEach-Object {
  Get-ChildItem $_.FullName -Directory | ForEach-Object { [void]$liveIds.Add($_.Name) }
}
Write-Output ("live session dirs=" + $liveIds.Count)
$inArchived = @($liveIds | Where-Object { $archived.Contains($_) })
Write-Output ("live dirs that are archived=" + $inArchived.Count)
if ($inArchived.Count -gt 0 -and $inArchived.Count -le 20) {
  $inArchived | ForEach-Object { Write-Output ("  archived: " + $_) }
}

Write-Output '--- table keys ---'
foreach ($prop in $w.tables.PSObject.Properties) {
  $name = $prop.Name
  $val = $prop.Value
  if ($null -eq $val) {
    Write-Output ("  {0}=null" -f $name)
    continue
  }
  if ($val -is [System.Array] -or ($val -is [System.Collections.IList])) {
    Write-Output ("  {0} list count={1}" -f $name, @($val).Count)
    continue
  }
  if ($val.PSObject -and $val.PSObject.Properties['rows']) {
    Write-Output ("  {0}.rows={1}" -f $name, @($val.rows).Count)
    continue
  }
  # workspace records often keyed by id
  $keys = @($val.PSObject.Properties.Name)
  Write-Output ("  {0} keys={1} sample={2}" -f $name, $keys.Count, (($keys | Select-Object -First 3) -join ','))
  foreach ($k in ($keys | Select-Object -First 3)) {
    $row = $val.$k
    if ($row.sessionIds) {
      Write-Output ("    {0} sessionIds={1}" -f $k, @($row.sessionIds).Count)
    } elseif ($row.PSObject.Properties['sessionIds']) {
      Write-Output ("    {0} sessionIds={1}" -f $k, @($row.sessionIds).Count)
    } else {
      $rowJson = ($row | ConvertTo-Json -Compress -Depth 3)
      if ($rowJson.Length -gt 200) { $rowJson = $rowJson.Substring(0, 200) + '...' }
      Write-Output ("    {0} => {1}" -f $k, $rowJson)
    }
  }
}
