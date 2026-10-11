/**
 * Skill credential cache — separate from UI sessionStore.
 * SEC-17: upstream tokens encrypted at rest (AES-256-GCM); plaintext only in memory.
 */
import { readFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { loadOrCreateSecretKey, sealSecret, openSecret } from './utils/secret-box.js'
import { atomicWriteJson } from './utils/atomic-write.js'

const DEFAULT_TTL_MS = 7 * 24 * 60 * 60 * 1000

export class SkillCredentialCache {
  /**
   * @param {{ file?: string, ttlMs?: number, logger?: Console, dataDir?: string }} opts
   */
  constructor(opts = {}) {
    this._file = opts.file || null
    this._dataDir = opts.dataDir || (opts.file ? dirname(opts.file) : null)
    this._ttlMs = opts.ttlMs ?? DEFAULT_TTL_MS
    this._logger = opts.logger || console
    /** @type {Map<string, { token: string, updatedAt: string, expiresAt: number }>} */
    this._map = new Map()
    this._dirty = false
    this._flushTimer = null
    /** @type {Buffer|null} */
    this._key = null
  }

  async init() {
    let hasEncryptedData = false
    if (this._file) {
      try {
        const peek = await readFile(this._file, 'utf-8')
        hasEncryptedData = /tokenEnc/.test(peek) && peek.trim().length > 2
      } catch { /* absent */ }
    }
    if (this._dataDir) {
      try {
        this._key = await loadOrCreateSecretKey(this._dataDir, { hasEncryptedData })
      } catch (err) {
        this._logger?.error?.('[uds-auth] secret key unavailable:', err.message)
        throw err
      }
    }
    if (!this._file) return
    try {
      const raw = await readFile(this._file, 'utf-8')
      const data = JSON.parse(raw)
      const entries = data?.entries && typeof data.entries === 'object' ? data.entries : data
      if (!entries || typeof entries !== 'object') return
      const now = Date.now()
      let decryptFailures = 0
      for (const [empNo, row] of Object.entries(entries)) {
        if (!row) continue
        const expiresAt = Number(row.expiresAt) || (now + this._ttlMs)
        if (expiresAt <= now) continue
        let token = null
        if (row.tokenEnc && this._key) {
          token = openSecret(this._key, row.tokenEnc)
          if (!token) decryptFailures++
        } else if (row.token) {
          // Legacy plaintext — accept once, rewrite encrypted on next flush.
          token = String(row.token)
          this._dirty = true
        }
        if (!token) continue
        this._map.set(String(empNo), {
          token,
          updatedAt: row.updatedAt || new Date().toISOString(),
          expiresAt,
        })
      }
      if (decryptFailures > 0) {
        this._logger?.error?.(
          '[uds-auth] skill credential decrypt failed for',
          decryptFailures,
          'entries — check secret key (not silently replaced)',
        )
      }
      if (this._dirty) this._scheduleFlush()
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
    if (typeof this._flushTimer.unref === 'function') this._flushTimer.unref()
  }

  async _flush() {
    if (!this._file || !this._dirty) return
    this._dirty = false
    if (!this._key) {
      this._logger?.error?.('[uds-auth] skillCredentialCache flush skipped: no key')
      this._dirty = true
      return
    }
    const entries = {}
    for (const [empNo, row] of this._map.entries()) {
      entries[empNo] = {
        tokenEnc: sealSecret(this._key, row.token),
        updatedAt: row.updatedAt,
        expiresAt: row.expiresAt,
      }
    }
    try {
      await atomicWriteJson(this._file, { entries, v: 2 }, { mode: 0o600 })
    } catch (err) {
      this._dirty = true
      this._logger?.warn?.('[uds-auth] skillCredentialCache flush failed:', err.message)
    }
  }
}

export function isLoopbackAddress(addr) {
  if (!addr) return false
  const a = String(addr).replace(/^::ffff:/i, '')
  return a === '127.0.0.1' || a === '::1' || a === 'localhost'
}

/**
 * Real socket peer only — never trust X-Forwarded-For / X-Real-IP (SEC-05).
 */
export function requestIsLoopback(req) {
  const ra = req?.socket?.remoteAddress
  return isLoopbackAddress(ra)
}
