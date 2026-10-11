/**
 * R06: short-lived task capabilities for skill/cron (not browser session bearers).
 * Bound to empNo + optional dshSessionId + audience + scope + expiry; revocable.
 */
import { createHash, randomBytes, timingSafeEqual } from 'node:crypto'

function hashToken(token) {
  return createHash('sha256').update(String(token)).digest('hex')
}

function safeEqualHex(a, b) {
  if (!a || !b || a.length !== b.length) return false
  try {
    return timingSafeEqual(Buffer.from(a, 'hex'), Buffer.from(b, 'hex'))
  } catch {
    return false
  }
}

export class TaskCapabilityStore {
  /**
   * @param {{ defaultTtlSeconds?: number, maxTtlSeconds?: number }} [opts]
   */
  constructor(opts = {}) {
    this._defaultTtl = Math.max(60, Number(opts.defaultTtlSeconds) || 3600)
    this._maxTtl = Math.max(this._defaultTtl, Number(opts.maxTtlSeconds) || 24 * 3600)
    /** @type {Map<string, object>} id → record */
    this._byId = new Map()
    /** @type {Map<string, string>} tokenHash → id */
    this._byHash = new Map()
  }

  /**
   * @param {{
   *   empNo: string,
   *   dshSessionId?: string|null,
   *   audience?: string,
   *   scopes?: string[],
   *   ttlSeconds?: number,
   *   mintedBy?: string,
   * }} input
   */
  mint(input) {
    for (const [id, row] of this._byId) {
      if (row.expiresAt <= Date.now()) this.revoke(id)
    }
    if (this._byId.size >= 5000) throw new Error('capability_capacity')
    const empNo = String(input?.empNo || '').trim()
    if (!empNo) throw new Error('capability_empNo_required')
    const ttl = Math.min(
      this._maxTtl,
      Math.max(30, Number(input.ttlSeconds) || this._defaultTtl),
    )
    const id = randomBytes(12).toString('hex')
    const token = randomBytes(32).toString('hex')
    const tokenHash = hashToken(token)
    const now = Date.now()
    const record = {
      id,
      tokenHash,
      empNo,
      dshSessionId: input.dshSessionId ? String(input.dshSessionId) : null,
      audience: String(input.audience || 'uds-auth-agent'),
      scopes: Array.isArray(input.scopes) ? input.scopes.map(String) : ['outbound', 'credentials'],
      mintedBy: input.mintedBy || null,
      createdAt: now,
      expiresAt: now + ttl * 1000,
      revoked: false,
    }
    this._byId.set(id, record)
    this._byHash.set(tokenHash, id)
    return {
      id,
      token,
      empNo: record.empNo,
      dshSessionId: record.dshSessionId,
      audience: record.audience,
      scopes: record.scopes,
      expiresAt: record.expiresAt,
      expiresIn: ttl,
    }
  }

  /**
   * @param {string} token
   * @param {{ audience?: string, scope?: string, dshSessionId?: string|null }} [opts]
   */
  verify(token, opts = {}) {
    const t = String(token || '').trim()
    if (!t || t.length < 16) return null
    const id = this._byHash.get(hashToken(t))
    if (!id) return null
    const row = this._byId.get(id)
    if (!row || row.revoked) return null
    if (row.expiresAt && Date.now() > row.expiresAt) {
      this.revoke(id)
      return null
    }
    if (!safeEqualHex(row.tokenHash, hashToken(t))) return null
    if (opts.audience && row.audience !== opts.audience) return null
    if (opts.scope && !(row.scopes || []).includes(opts.scope)) return null
    if (opts.dshSessionId != null && row.dshSessionId
      && String(opts.dshSessionId) !== String(row.dshSessionId)) {
      return null
    }
    return {
      id: row.id,
      empNo: row.empNo,
      dshSessionId: row.dshSessionId,
      audience: row.audience,
      scopes: [...(row.scopes || [])],
      expiresAt: row.expiresAt,
    }
  }

  revoke(id) {
    const row = this._byId.get(String(id || ''))
    if (!row) return false
    row.revoked = true
    this._byHash.delete(row.tokenHash)
    this._byId.delete(row.id)
    return true
  }

  revokeEmpNo(empNo) {
    const e = String(empNo || '').trim()
    let n = 0
    for (const [id, row] of [...this._byId]) {
      if (row.empNo === e) {
        this.revoke(id)
        n++
      }
    }
    return n
  }

  extractFromRequest(req) {
    const h = req?.headers || {}
    return (
      h['x-uds-task-capability']
      || h['X-UDS-Task-Capability']
      || null
    )
  }
}
