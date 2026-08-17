# Resolve a proxy URL for the WhatsApp sidecar without hardcoding a port.
# Order: process env -> state\proxy.url -> Windows user Internet Settings.
function Get-OclawWhatsAppProxyUrl {
  param(
    [Parameter(Mandatory = $true)][string]$StateDir,
    [switch]$Persist
  )
  $found = ""
  foreach ($name in @("AIA_WHATSAPP_PROXY_URL", "HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")) {
    $val = [Environment]::GetEnvironmentVariable($name, "Process")
    if ($val -and $val.Trim()) {
      $found = $val.Trim()
      break
    }
  }
  if (-not $found) {
    $proxyFile = Join-Path $StateDir "proxy.url"
    if (Test-Path $proxyFile) {
      $line = @(Get-Content -Path $proxyFile -ErrorAction SilentlyContinue) | Select-Object -First 1
      if ($line -and $line.Trim()) { $found = $line.Trim() }
    }
  }
  if (-not $found) {
    try {
      $reg = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -ErrorAction Stop
      $raw = [string]$reg.ProxyServer
      # Clash TUN often sets ProxyEnable=0 but leaves the last mixed-port address.
      if ($raw -and (($reg.ProxyEnable -eq 1) -or ($raw -match '(?i)127\.0\.0\.1|localhost|::1'))) {
        $hostport = ""
        if ($raw -match '(?i)https?=([^;]+)') {
          $hostport = $Matches[1].Trim()
        } elseif ($raw -match '^[^\s;]+$') {
          $hostport = $raw.Trim()
        }
        if ($hostport) {
          if ($hostport -notmatch '^[a-zA-Z][a-zA-Z0-9+.-]*://') {
            $hostport = "http://$hostport"
          }
          $found = $hostport
        }
      }
    } catch {}
  }
  if ($found -and $found.StartsWith('"') -and $found.EndsWith('"')) {
    $found = $found.Substring(1, $found.Length - 2)
  }
  if ($Persist -and $found) {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    Set-Content -Path (Join-Path $StateDir "proxy.url") -Value $found -Encoding ascii
  }
  return $found
}
