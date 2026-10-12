import { createHash, randomBytes, timingSafeEqual } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { SessionStore, SESSION_ABSOLUTE_MAX_SECONDS } from './store.js'
import { atomicWriteJson } from '../utils/atomic-write.js'
import { loadOrCreateSecretKey, sealSecret, openSecret } from '../utils/secret-box.js'

function hashBearer(bearer) {
  return createHash('sha256').update(String(bearer)).digest('hex')
}

function safeEqualHex(a, b) {
  if (!a || !b || a.length !== b.length) return false
  try {
    return timingSafeEqual(Buffer.from(a, 'hex'), Buffer.from(b, 'hex'))
  } catch {
    return false
  }
}

/**
 * In-memory auth session store, optionally persisted so a Host restart does not
 * log everyone out (emergency admins have no SSO re-mint path).
 * Primary key: sessionId. Auth proof: bearer (stored as SHA-256 hash only).
 * empNo is a secondary index for logout-all / listing — not an auth credential.
 *
 * Persistence (opts.file + opts.dataDir): bearer hashes and expiry in clear,
 * userData (may carry the UAC token) sealed with the plugin AES-GCM key.
 */
export class MemoryStore extends SessionStore {
  /**
   * @param {{ file?: string, dataDir?: string, logger?: any }} [opts]
   */
  constructor(opts = {}) {
    super()
    this._file = opts.file || null
    this._dataDir = opts.dataDir || null
    this._logger = opts.logger || console
    this._key = null
    this._saveTimer = null
    /** @type {Map<string, object>} sessionId → record */
    this._sessions = new Map()
    /** @type {Map<string, string>} bearerHash → sessionId */
    this._byBearer = new Map()
    /** @type {Map<string, Set<string>>} empNo → sessionIds */
    this._byEmpNo = new Map()
    /** @type {Map<string, object>} empNo → profile (cache only) */
    this._profiles = new Map()
    /** @type {Map<string, NodeJS.Timeout>} */
    this._timers = new Map()
  }

  /** Load persisted sessions (if configured). Never throws: bad state is dropped. */
  async init() {
    if (!this._file) return
    let raw = null
    try {
      raw = JSON.parse(await readFile(this._file, 'utf-8'))
    } catch (err) {
      if (err?.code !== 'ENOENT') this._logger.warn?.('[uds-auth:sessions] load failed, starting empty:', err.message)
    }
    const rows = Array.isArray(raw?.sessions) ? raw.sessions : []
    try {
      this._key = await loadOrCreateSecretKey(this._dataDir || '.', { hasEncryptedData: rows.length > 0 })
    } catch (err) {
      this._logger.warn?.('[uds-auth:sessions] secret key unavailable, sessions will not persist:', err.code || err.message)
      this._file = null
      return
    }
    const now = Date.now()
    let restored = 0
    for (const r of rows) {
      if (!r?.sessionId || !r.bearerHash || !r.empNo) continue
      if (!(r.expiresAt > now) || !(r.absoluteExpiresAt > now)) continue
      const plain = openSecret(this._key, r.userData)
      if (plain == null) continue
      let userData
      try { userData = JSON.parse(plain) } catch { continue }
      const record = {
        sessionId: String(r.sessionId),
        bearerHash: String(r.bearerHash),
        empNo: String(r.empNo),
        kind: String(r.kind || 'uds'),
        userData,
        createdAt: Number(r.createdAt) || now,
        expiresAt: Number(r.expiresAt),
        absoluteExpiresAt: Number(r.absoluteExpiresAt),
      }
      this._sessions.set(record.sessionId, record)
      this._byBearer.set(record.bearerHash, record.sessionId)
      if (!this._byEmpNo.has(record.empNo)) this._byEmpNo.set(record.empNo, new Set())
      this._byEmpNo.get(record.empNo).add(record.sessionId)
      this._scheduleExpiry(record.sessionId, Math.ceil((record.expiresAt - now) / 1000))
      if (userData.displayName || userData.username) {
        this._profiles.set(record.empNo, {
          empNo: record.empNo,
          username: userData.username,
          displayName: userData.displayName,
          department: userData.department,
          organization: userData.organization,
          email: userData.email,
          phone: userData.phone,
        })
      }
      restored++
    }
    if (restored !== rows.length) this._scheduleSave()
    if (restored) this._logger.info?.('[uds-auth:sessions] restored %d session(s)', restored)
  }

  _scheduleSave() {
    if (!this._file || !this._key || this._saveTimer) return
    this._saveTimer = setTimeout(() => {
      this._saveTimer = null
      void this.flush()
    }, 200)
    if (typeof this._saveTimer.unref === 'function') this._saveTimer.unref()
  }

  /** Write current sessions now (also used on shutdown / tests). */
  async flush() {
    if (!this._file || !this._key) return
    if (this._saveTimer) {
      clearTimeout(this._saveTimer)
      this._saveTimer = null
    }
    const now = Date.now()
    const sessions = []
    for (const row of this._sessions.values()) {
      if (!(row.expiresAt > now) || !(row.absoluteExpiresAt > now)) continue
      sessions.push({
        sessionId: row.sessionId,
        bearerHash: row.bearerHash,
        empNo: row.empNo,
        kind: row.kind,
        createdAt: row.createdAt,
        expiresAt: row.expiresAt,
        absoluteExpiresAt: row.absoluteExpiresAt,
        userData: sealSecret(this._key, JSON.stringify(row.userData || {})),
      })
    }
    try {
      await atomicWriteJson(this._file, { version: 1, sessions }, { mode: 0o600 })
    } catch (err) {
      this._logger.warn?.('[uds-auth:sessions] save failed:', err.message)
    }
  }

  _purgeExpired(sessionId) {
    const row = this._sessions.get(sessionId)
    if (!row) return null
    if (row.expiresAt && Date.now() > row.expiresAt) {
      this._removeRecord(sessionId, row)
      return null
    }
    return row
  }

  _removeRecord(sessionId, row) {
    if (this._sessions.has(sessionId)) this._scheduleSave()
    this._sessions.delete(sessionId)
    if (row?.bearerHash) this._byBearer.delete(row.bearerHash)
    if (row?.empNo) {
      const set = this._byEmpNo.get(row.empNo)
      if (set) {
        set.delete(sessionId)
        if (set.size === 0) this._byEmpNo.delete(row.empNo)
      }
    }
    if (this._timers.has(sessionId)) {
      clearTimeout(this._timers.get(sessionId))
      this._timers.delete(sessionId)
    }
  }

  _scheduleExpiry(sessionId, ttlSeconds) {
    if (this._timers.has(sessionId)) {
      clearTimeout(this._timers.get(sessionId))
      this._timers.delete(sessionId)
    }
    if (!ttlSeconds || ttlSeconds <= 0) return
    const timer = setTimeout(() => {
      const row = this._sessions.get(sessionId)
      if (row) this._removeRecord(sessionId, row)
    }, ttlSeconds * 1000)
    // Do not keep the process alive solely for session TTLs (tests / short-lived hosts).
    if (typeof timer.unref === 'function') timer.unref()
    this._timers.set(sessionId, timer)
  }

  _publicRecord(row) {
    if (!row) return null
    return {
      sessionId: row.sessionId,
      empNo: row.empNo,
      kind: row.kind,
      userData: { ...row.userData },
      createdAt: row.createdAt,
      expiresAt: row.expiresAt,
      absoluteExpiresAt: row.absoluteExpiresAt,
    }
  }

  async create(userData, ttlSeconds = 1800) {
    const empNo = String(userData?.empNo || '').trim()
    if (!empNo) throw new Error('session_empNo_required')
    const sessionId = randomBytes(16).toString('hex')
    const bearer = randomBytes(32).toString('hex')
    const bearerHash = hashBearer(bearer)
    const now = Date.now()
    const ttl = Math.max(60, Number(ttlSeconds) || 1800)
    // Idle TTL slides via touch(); absolute lifetime is a fixed 7 days. (Was min(ttl, 7d),
    // which capped every session at its 30-min idle TTL and made sliding a no-op.)
    const absoluteCap = SESSION_ABSOLUTE_MAX_SECONDS
    const record = {
      sessionId,
      bearerHash,
      empNo,
      kind: (() => {
        const mode = String(userData?.authMode || '')
        if (mode.includes('local-admin') || mode === 'sealed_box' || mode === 'local_admin') {
          return 'sealed_box'
        }
        if (mode.includes('fallback') || mode === 'fallback-password' || mode === 'fallback-login') {
          return 'fallback'
        }
        if (empNo === 'administrator') return 'fallback'
        return 'uds'
      })(),
      userData: { ...userData },
      createdAt: now,
      expiresAt: now + ttl * 1000,
      absoluteExpiresAt: now + absoluteCap * 1000,
    }
    this._sessions.set(sessionId, record)
    this._byBearer.set(bearerHash, sessionId)
    if (!this._byEmpNo.has(empNo)) this._byEmpNo.set(empNo, new Set())
    this._byEmpNo.get(empNo).add(sessionId)
    this._scheduleExpiry(sessionId, ttl)
    this._scheduleSave()
    if (userData.displayName || userData.username) {
      this._profiles.set(empNo, {
        empNo,
        username: userData.username,
        displayName: userData.displayName,
        department: userData.department,
        organization: userData.organization,
        email: userData.email,
        phone: userData.phone,
      })
    }
    return { sessionId, bearer, record: this._publicRecord(record) }
  }

  _lookupBearer(bearer) {
    const t = String(bearer || '').trim()
    if (!t || t.length < 16) return null
    const sessionId = this._byBearer.get(hashBearer(t))
    if (!sessionId) return null
    const row = this._purgeExpired(sessionId)
    if (!row) return null
    if (!safeEqualHex(row.bearerHash, hashBearer(t))) return null
    if (row.absoluteExpiresAt && Date.now() > row.absoluteExpiresAt) {
      this._removeRecord(sessionId, row)
      return null
    }
    return row
  }

  async getByBearer(bearer) {
    return this._publicRecord(this._lookupBearer(bearer))
  }

  getByBearerSync(bearer) {
    return this._publicRecord(this._lookupBearer(bearer))
  }

  async getBySessionId(sessionId) {
    const id = String(sessionId || '').trim()
    if (!id) return null
    return this._publicRecord(this._purgeExpired(id))
  }

  async listUdsSessionsForValidation() {
    const sessions = []
    for (const [sessionId, record] of this._sessions) {
      const row = this._purgeExpired(sessionId)
      if (!row || row.kind !== 'uds') continue
      sessions.push({
        sessionId: row.sessionId,
        empNo: row.empNo,
        token: typeof row.userData?.token === 'string' ? row.userData.token : '',
        createdAt: row.createdAt,
      })
    }
    return sessions
  }

  getBySessionIdSync(sessionId) {
    const id = String(sessionId || '').trim()
    if (!id) return null
    return this._publicRecord(this._purgeExpired(id))
  }

  async touch(sessionId, ttlSeconds) {
    const row = this._purgeExpired(String(sessionId || ''))
    if (!row) return null
    const ttl = Math.max(60, Number(ttlSeconds) || 1800)
    const absLeft = row.absoluteExpiresAt
      ? Math.max(0, Math.floor((row.absoluteExpiresAt - Date.now()) / 1000))
      : ttl
    const nextTtl = Math.min(ttl, absLeft || ttl)
    if (nextTtl <= 0) {
      this._removeRecord(row.sessionId, row)
      return null
    }
    row.expiresAt = Date.now() + nextTtl * 1000
    row.userData = {
      ...row.userData,
      lastActiveAt: new Date().toISOString(),
    }
    this._scheduleExpiry(row.sessionId, nextTtl)
    this._scheduleSave()
    return this._publicRecord(row)
  }

  async revokeSession(sessionId) {
    const row = this._sessions.get(String(sessionId || ''))
    if (!row) return false
    this._removeRecord(row.sessionId, row)
    return true
  }

  async revokeBearer(bearer) {
    const row = this._lookupBearer(bearer)
    if (!row) return false
    this._removeRecord(row.sessionId, row)
    return true
  }

  async revokeEmpNo(empNo) {
    const e = String(empNo || '').trim()
    const set = this._byEmpNo.get(e)
    if (!set) return 0
    let n = 0
    for (const sid of [...set]) {
      const row = this._sessions.get(sid)
      if (row) {
        this._removeRecord(sid, row)
        n++
      }
    }
    return n
  }

  /**
   * D04: revoke only sessions matching predicate (e.g. password-mode, not sealed-box).
   * @param {string} empNo
   * @param {(row: object) => boolean} predicate
   */
  async revokeEmpNoMatching(empNo, predicate) {
    const e = String(empNo || '').trim()
    const set = this._byEmpNo.get(e)
    if (!set || typeof predicate !== 'function') return 0
    let n = 0
    for (const sid of [...set]) {
      const row = this._sessions.get(sid)
      if (row && predicate(row)) {
        this._removeRecord(sid, row)
        n++
      }
    }
    return n
  }

  async setProfile(empNo, profile) {
    const e = String(empNo || '').trim()
    if (!e || !profile) return
    this._profiles.set(e, { ...profile, empNo: e })
  }

  async getProfile(empNo) {
    const row = this._profiles.get(String(empNo || '').trim())
    return row ? { ...row } : null
  }

  async clear() {
    this._scheduleSave()
    for (const t of this._timers.values()) clearTimeout(t)
    this._timers.clear()
    this._sessions.clear()
    this._byBearer.clear()
    this._byEmpNo.clear()
    this._profiles.clear()
  }

  /**
   * Legacy: return first active session userData for empNo (profile-like).
   * Does NOT prove the caller is authenticated as that empNo.
   */
  async get(empNo) {
    const e = String(empNo || '').trim()
    const set = this._byEmpNo.get(e)
    if (!set || set.size === 0) return null
    for (const sid of set) {
      const row = this._purgeExpired(sid)
      if (row) return { ...row.userData, _sessionId: row.sessionId }
    }
    return null
  }

  /**
   * Legacy compat: create a new session for empNo (multi-device safe).
   * Returns the public userData; caller should also capture bearer via create().
   */
  async setex(empNo, seconds, userData) {
    const data = { ...userData, empNo: String(empNo) }
    const { bearer, sessionId, record } = await this.create(data, seconds)
    // Stash last mint so login handlers can read bearer without API break.
    this._lastMint = { empNo: String(empNo), bearer, sessionId }
    return record.userData
  }

  takeLastMint() {
    const m = this._lastMint || null
    this._lastMint = null
    return m
  }

  async delete(empNo) {
    await this.revokeEmpNo(empNo)
  }

  async has(empNo) {
    const e = String(empNo || '').trim()
    const set = this._byEmpNo.get(e)
    if (!set) return false
    for (const sid of set) {
      if (this._purgeExpired(sid)) return true
    }
    return false
  }

  async keys() {
    const out = new Set()
    for (const [empNo, set] of this._byEmpNo) {
      for (const sid of set) {
        if (this._purgeExpired(sid)) {
          out.add(empNo)
          break
        }
      }
    }
    return [...out]
  }
}
