/**
 * Skill credential cache — separate from UI sessionStore.
 * empNo → { token, updatedAt }; long TTL for cron/skills after UI logout.
 */
import { readFile, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { mkdir } from 'node:fs/promises'

const DEFAULT_TTL_MS = 7 * 24 * 60 * 60 * 1000

export class SkillCredentialCache {
  /**
   * @param {{ file?: string, ttlMs?: number, logger?: Console }} opts
   */
  constructor(opts = {}) {
    this._file = opts.file || null
    this._ttlMs = opts.ttlMs ?? DEFAULT_TTL_MS
    this._logger = opts.logger || console
    /** @type {Map<string, { token: string, updatedAt: string, expiresAt: number }>} */
    this._map = new Map()
    this._dirty = false
    this._flushTimer = null
  }

  async init() {
    if (!this._file) return
    try {
      const raw = await readFile(this._file, 'utf-8')
      const data = JSON.parse(raw)
      const entries = data?.entries && typeof data.entries === 'object' ? data.entries : data
      if (!entries || typeof entries !== 'object') return
      const now = Date.now()
      for (const [empNo, row] of Object.entries(entries)) {
        if (!row?.token) continue
        const expiresAt = Number(row.expiresAt) || (now + this._ttlMs)
        if (expiresAt <= now) continue
        this._map.set(String(empNo), {
          token: String(row.token),
          updatedAt: row.updatedAt || new Date().toISOString(),
          expiresAt,
        })
      }
    } catch {
      /* optional file */
    }
  }

  /**
   * @param {string} empNo
   * @param {string} token
   */
  set(empNo, token) {
    if (!empNo || !token) return
    if (String(empNo).startsWith('__')) return
    if (empNo === 'administrator') return
    const now = Date.now()
    this._map.set(String(empNo), {
      token: String(token),
      updatedAt: new Date().toISOString(),
      expiresAt: now + this._ttlMs,
    })
    this._scheduleFlush()
  }

  /**
   * @param {string} empNo
   * @returns {{ empNo: string, token: string, updatedAt: string } | null}
   */
  get(empNo) {
    if (!empNo) return null
    const key = String(empNo)
    const row = this._map.get(key)
    if (!row) return null
    if (row.expiresAt && Date.now() > row.expiresAt) {
      this._map.delete(key)
      this._scheduleFlush()
      return null
    }
    return { empNo: key, token: row.token, updatedAt: row.updatedAt }
  }

  /**
   * @param {string} empNo
   */
  delete(empNo) {
    if (!empNo) return
    if (this._map.delete(String(empNo))) this._scheduleFlush()
  }

  _scheduleFlush() {
    if (!this._file) return
    this._dirty = true
    if (this._flushTimer) return
    this._flushTimer = setTimeout(() => {
      this._flushTimer = null
      void this._flush()
    }, 250)
  }

  async _flush() {
    if (!this._file || !this._dirty) return
    this._dirty = false
    const entries = {}
    for (const [empNo, row] of this._map.entries()) {
      entries[empNo] = {
        token: row.token,
        updatedAt: row.updatedAt,
        expiresAt: row.expiresAt,
      }
    }
    try {
      await mkdir(dirname(this._file), { recursive: true })
      await writeFile(this._file, JSON.stringify({ entries }, null, 2), 'utf-8')
    } catch (err) {
      this._logger?.warn?.('[uds-auth] skillCredentialCache flush failed:', err.message)
    }
  }
}

export function isLoopbackAddress(addr) {
  if (!addr) return false
  const a = String(addr).replace(/^::ffff:/i, '')
  return a === '127.0.0.1' || a === '::1' || a === 'localhost'
}

export function requestIsLoopback(req) {
  const ra = req?.socket?.remoteAddress
  if (isLoopbackAddress(ra)) return true
  const xf = String(req?.headers?.['x-forwarded-for'] || '').split(',')[0].trim()
  if (xf && isLoopbackAddress(xf)) return true
  return false
}
