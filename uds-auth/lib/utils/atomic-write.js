/**
 * SEC-21: atomic JSON replace — write temp in same dir, then rename.
 */
import { open, rename, mkdir, unlink } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { randomBytes } from 'node:crypto'

/**
 * @param {string} filePath
 * @param {string|Buffer} data
 * @param {{ mode?: number }} [opts]
 */
export async function atomicWriteFile(filePath, data, opts = {}) {
  const dir = dirname(filePath)
  await mkdir(dir, { recursive: true })
  const tmp = join(dir, `.${randomBytes(8).toString('hex')}.tmp`)
  const mode = opts.mode ?? 0o600
  let handle, committed = false
  try {
    handle = await open(tmp, 'wx', mode)
    await handle.writeFile(data, typeof data === 'string' ? 'utf-8' : undefined)
    await handle.sync()
    await handle.close()
    handle = null
    await rename(tmp, filePath)
    committed = true
    if (process.platform !== 'win32') {
      // Rename is the commit point. A filesystem that cannot fsync directories
      // must not make callers roll back memory after the replacement succeeded.
      let directory
      try { directory = await open(dir, 'r'); await directory.sync() }
      catch { /* directory durability is best effort on unsupported filesystems */ }
      finally { await directory?.close().catch(() => {}) }
    }
  } finally {
    await handle?.close()
    if (!committed) await unlink(tmp).catch(err => { if (err.code !== 'ENOENT') throw err })
  }
}

/**
 * @param {string} filePath
 * @param {any} obj
 * @param {{ mode?: number, pretty?: boolean }} [opts]
 */
export async function atomicWriteJson(filePath, obj, opts = {}) {
  const text = opts.pretty === false
    ? JSON.stringify(obj)
    : JSON.stringify(obj, null, 2)
  await atomicWriteFile(filePath, text + '\n', { mode: opts.mode })
}
