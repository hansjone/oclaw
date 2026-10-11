import { readFile, copyFile, unlink, lstat } from 'node:fs/promises'
import { constants } from 'node:fs'
import { resolve } from 'node:path'
import { atomicWriteJson } from './utils/atomic-write.js'

export const SECURITY_STATE_FILES = ['roles.json', 'session-owners.json', 'user-workspaces.json',
  'session-bridge.json', 'skill-credentials.json', 'config.runtime.json', '.uds-auth-secret-key']

async function readOptional(path) {
  try {
    const stat = await lstat(path)
    if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('legacy_migrate_unsafe_file')
    return await readFile(path)
  } catch (err) { if (err.code === 'ENOENT') return null; throw err }
}

/** Exclusive copies, no overwrite, identical partial copies can resume after a crash. */
export async function migrateState(dataDir, sourceDir, logger = console, io = {}) {
  const marker = resolve(dataDir, '.uds-auth-migrated-from-install')
  if (await readOptional(marker)) return { migrated: false, reason: 'already' }
  const present = []
  for (const name of SECURITY_STATE_FILES) {
    const bytes = await readOptional(resolve(sourceDir, name))
    if (bytes) present.push({ name, bytes })
  }
  if (!present.length) return { migrated: false, reason: 'no_legacy' }
  for (const { name, bytes } of present) {
    const existing = await readOptional(resolve(dataDir, name))
    if (existing && !existing.equals(bytes)) {
      throw Object.assign(new Error('legacy_migrate_conflict'), { code: 'legacy_migrate_conflict', conflicts: [name] })
    }
  }
  const copied = []
  try {
    for (const { name, bytes } of present) {
      const dest = resolve(dataDir, name)
      try {
        await (io.copyFile || copyFile)(resolve(sourceDir, name), dest, constants.COPYFILE_EXCL)
        copied.push(name)
      } catch (err) {
        if (err.code !== 'EEXIST' || !(await readOptional(dest))?.equals(bytes)) throw err
      }
      if (!(await readOptional(dest))?.equals(bytes)) throw new Error('legacy_migrate_source_changed')
    }
    await atomicWriteJson(marker, { at: new Date().toISOString(), from: resolve(sourceDir),
      copied, seen: present.map(row => row.name) })
  } catch (err) {
    // Remove only files created by this attempt which still equal the source snapshot.
    for (const name of copied) {
      const dest = resolve(dataDir, name)
      const bytes = present.find(row => row.name === name).bytes
      try { if ((await readOptional(dest))?.equals(bytes)) await unlink(dest) } catch { /* preserve evidence */ }
    }
    logger.error?.('[uds-auth] legacy migration failed; no success marker written')
    throw err
  }
  logger.info?.('[uds-auth] legacy state migration committed')
  return { migrated: true, copied, present: present.map(row => row.name) }
}
