import { lstat, chmod } from 'node:fs/promises'
import { resolve } from 'node:path'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { SECURITY_STATE_FILES } from './state-migration.js'
const run = promisify(execFile)

/** Restrict the owned profile, including legacy files with explicit broad ACLs. */
export async function protectProfileDirectory(dataDir) {
  const root = resolve(dataDir)
  const dir = await lstat(root)
  if (!dir.isDirectory() || dir.isSymbolicLink()) throw new Error('profile_directory_unsafe')
  const files = []
  for (const name of [...SECURITY_STATE_FILES, '.uds-auth-migrated-from-install']) {
    const path = resolve(root, name)
    try {
      const stat = await lstat(path)
      if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('profile_state_file_unsafe')
      files.push(name)
    } catch (err) { if (err.code !== 'ENOENT') throw err }
  }
  if (process.platform !== 'win32') {
    await chmod(root, 0o700)
    for (const name of files) await chmod(resolve(root, name), 0o600)
    return { platform: process.platform, directoryMode: '0700', fileMode: '0600', files: files.length }
  }
  // LiteralPath + child-only environment avoids shell/path interpolation.
  const script = `
$ErrorActionPreference = 'Stop'
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$system = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$paths = @($env:UDS_ACL_ROOT)
$names = ConvertFrom-Json $env:UDS_ACL_FILES
foreach ($name in $names) { $paths += Join-Path $env:UDS_ACL_ROOT $name }
foreach ($path in $paths) {
  $isDir = [System.IO.Directory]::Exists($path)
  if ($isDir) {
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $inherit = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
  } else {
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $inherit = [System.Security.AccessControl.InheritanceFlags]::None
  }
  $acl.SetAccessRuleProtection($true, $false)
  $acl.SetOwner($sid)
  foreach ($principal in @($sid, $system)) {
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($principal, 'FullControl', $inherit, 'None', 'Allow')
    $acl.AddAccessRule($rule)
  }
  if ($isDir) {
    [System.IO.Directory]::SetAccessControl($path, $acl)
    $check = [System.IO.Directory]::GetAccessControl($path)
  } else {
    [System.IO.File]::SetAccessControl($path, $acl)
    $check = [System.IO.File]::GetAccessControl($path)
  }
  if (!$check.AreAccessRulesProtected) { throw 'profile_acl_inheritance' }
  $rules = $check.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])
  if ($rules.Count -ne 2) { throw 'profile_acl_rule_count' }
  foreach ($rule in $rules) {
    if ($rule.IdentityReference.Value -notin @($sid.Value, $system.Value) -or $rule.AccessControlType -ne 'Allow') { throw 'profile_acl_unexpected_principal' }
  }
}
@{ platform = 'win32'; protected = $true; principals = @('current-user', 'SYSTEM'); files = $names.Count } | ConvertTo-Json -Compress
`
  try {
    const { stdout } = await run('powershell.exe', ['-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script], {
      windowsHide: true, timeout: 30_000, env: { ...process.env, UDS_ACL_ROOT: root, UDS_ACL_FILES: JSON.stringify(files) },
    })
    return JSON.parse(stdout.trim())
  } catch (cause) {
    throw Object.assign(new Error('profile_acl_failed'), { code: 'profile_acl_failed', cause })
  }
}
