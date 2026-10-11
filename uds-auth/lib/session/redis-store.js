import { createHash, randomBytes } from 'node:crypto'
import { SessionStore, SESSION_ABSOLUTE_MAX_SECONDS } from './store.js'

function hashBearer(bearer) {
  return createHash('sha256').update(String(bearer)).digest('hex')
}

/**
 * Redis-backed auth session store.
 * Keys: uds-sess:{sessionId}, uds-bearer:{hash} → sessionId, uds-emp:{empNo} set
 */
export class RedisStore extends SessionStore {
  constructor(redisClient) {
    super()
    if (!redisClient) throw new Error('Redis client is required')
    this._client = redisClient
    this._lastMint = null
  }

  _sessKey(id) { return `uds-sess:${id}` }
  _bearerKey(hash) { return `uds-bearer:${hash}` }
  _empKey(empNo) { return `uds-emp:${empNo}` }
  _profileKey(empNo) { return `uds-profile:${empNo}` }

  async create(userData, ttlSeconds = 1800) {
    const empNo = String(userData?.empNo || '').trim()
    if (!empNo) throw new Error('session_empNo_required')
    const sessionId = randomBytes(16).toString('hex')
    const bearer = randomBytes(32).toString('hex')
    const bearerHash = hashBearer(bearer)
    const now = Date.now()
    const ttl = Math.max(60, Number(ttlSeconds) || 1800)
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
      absoluteExpiresAt: now + SESSION_ABSOLUTE_MAX_SECONDS * 1000,
    }
    const payload = JSON.stringify(record)
    await this._client.setEx(this._sessKey(sessionId), ttl, payload)
    await this._client.setEx(this._bearerKey(bearerHash), ttl, sessionId)
    await this._client.sAdd(this._empKey(empNo), sessionId)
    await this._client.expire(this._empKey(empNo), ttl)
    this._lastMint = { empNo, bearer, sessionId }
    return {
      sessionId,
      bearer,
      record: {
        sessionId,
        empNo,
        kind: record.kind,
        userData: { ...userData },
        createdAt: record.createdAt,
        expiresAt: record.expiresAt,
        absoluteExpiresAt: record.absoluteExpiresAt,
      },
    }
  }

  async _load(sessionId) {
    if (!sessionId) return null
    const raw = await this._client.get(this._sessKey(sessionId))
    if (!raw) return null
    try {
      const row = JSON.parse(raw)
      if (row.absoluteExpiresAt && Date.now() > row.absoluteExpiresAt) {
        await this.revokeSession(sessionId)
        return null
      }
      return row
    } catch {
      return null
    }
  }

  _public(row) {
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

  async getByBearer(bearer) {
    const t = String(bearer || '').trim()
    if (!t || t.length < 16) return null
    const sessionId = await this._client.get(this._bearerKey(hashBearer(t)))
    return this._public(await this._load(sessionId))
  }

  getByBearerSync() {
    // Redis cannot sync-read; callers must use async path or MemoryStore.
    return null
  }

  async getBySessionId(sessionId) {
    return this._public(await this._load(String(sessionId || '').trim()))
  }

  async touch(sessionId, ttlSeconds) {
    const row = await this._load(sessionId)
    if (!row) return null
    const ttl = Math.max(60, Number(ttlSeconds) || 1800)
    const absLeft = row.absoluteExpiresAt
      ? Math.max(0, Math.floor((row.absoluteExpiresAt - Date.now()) / 1000))
      : ttl
    const nextTtl = Math.min(ttl, absLeft || ttl)
    if (nextTtl <= 0) {
      await this.revokeSession(sessionId)
      return null
    }
    row.expiresAt = Date.now() + nextTtl * 1000
    row.userData = { ...row.userData, lastActiveAt: new Date().toISOString() }
    await this._client.setEx(this._sessKey(sessionId), nextTtl, JSON.stringify(row))
    await this._client.setEx(this._bearerKey(row.bearerHash), nextTtl, sessionId)
    return this._public(row)
  }

  async revokeSession(sessionId) {
    const row = await this._load(sessionId)
    if (!row) {
      await this._client.del(this._sessKey(sessionId))
      return false
    }
    await this._client.del(this._sessKey(sessionId))
    await this._client.del(this._bearerKey(row.bearerHash))
    await this._client.sRem(this._empKey(row.empNo), sessionId)
    return true
  }

  async revokeBearer(bearer) {
    const t = String(bearer || '').trim()
    if (!t) return false
    const sessionId = await this._client.get(this._bearerKey(hashBearer(t)))
    if (!sessionId) return false
    return this.revokeSession(sessionId)
  }

  async revokeEmpNo(empNo) {
    const e = String(empNo || '').trim()
    const members = await this._client.sMembers(this._empKey(e))
    let n = 0
    for (const sid of members || []) {
      if (await this.revokeSession(sid)) n++
    }
    await this._client.del(this._empKey(e))
    return n
  }

  async setProfile(empNo, profile) {
    const e = String(empNo || '').trim()
    if (!e || !profile) return
    await this._client.set(this._profileKey(e), JSON.stringify({ ...profile, empNo: e }))
  }

  async getProfile(empNo) {
    const raw = await this._client.get(this._profileKey(String(empNo || '').trim()))
    if (!raw) return null
    try { return JSON.parse(raw) } catch { return null }
  }

  async clear() {
    const keys = await this._client.keys('uds-sess:*')
    const bkeys = await this._client.keys('uds-bearer:*')
    const ekeys = await this._client.keys('uds-emp:*')
    const pkeys = await this._client.keys('uds-profile:*')
    const all = [...keys, ...bkeys, ...ekeys, ...pkeys]
    if (all.length) await this._client.del(all)
  }

  async get(empNo) {
    const members = await this._client.sMembers(this._empKey(String(empNo || '').trim()))
    for (const sid of members || []) {
      const row = await this._load(sid)
      if (row) return { ...row.userData, _sessionId: row.sessionId }
    }
    return null
  }

  async setex(empNo, seconds, userData) {
    const { bearer, sessionId, record } = await this.create(
      { ...userData, empNo: String(empNo) },
      seconds,
    )
    this._lastMint = { empNo: String(empNo), bearer, sessionId }
    return record.userData
  }

  takeLastMint() {
    const m = this._lastMint
    this._lastMint = null
    return m
  }

  async delete(empNo) {
    await this.revokeEmpNo(empNo)
  }

  async has(empNo) {
    return !!(await this.get(empNo))
  }

  async keys() {
    const ekeys = await this._client.keys('uds-emp:*')
    return ekeys.map((k) => k.replace(/^uds-emp:/, ''))
  }
}
