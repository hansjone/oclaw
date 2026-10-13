/**
 * Cookie-less session bridge for Desktop (dsh-app:// drops Set-Cookie / document.cookie).
 *
 * Login handlers mint a random token; the browser stores { empNo, token, kind } in
 * localStorage and sends X-UDS-Bridge-* headers on subsequent /uds-auth requests.
 */
import { randomBytes, timingSafeEqual, createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { atomicWriteJson } from './utils/atomic-write.js'

export const BRIDGE_EMPNO_HEADER = 'x-uds-bridge-empno'
export const BRIDGE_TOKEN_HEADER = 'x-uds-bridge-token'
export const BRIDGE_KIND_HEADER = 'x-uds-bridge-kind'

const DEFAULT_TTL_MS = 7 * 24 * 60 * 60 * 1000

function safeEqualStr(a, b) {
  if (a == null || b == null) return false
  const ha = createHash('sha256').update(String(a)).digest()
  const hb = createHash('sha256').update(String(b)).digest()
  return timingSafeEqual(ha, hb)
}

export class SessionBridgeStore {
  /**
   * @param {{ file?: string, ttlMs?: number }} [opts]
   */
  constructor(opts = {}) {
    this._file = opts.file || null
    this._ttlMs = opts.ttlMs || DEFAULT_TTL_MS
    /** @type {Map<string, { empNo: string, kind: string, exp: number, ssoToken?: string }>} */
    this._byToken = new Map()
    /** @type {Map<string, { empNo: string, bearer: string, exp: number }>} T01: one-time WS tickets */
    this._wsTickets = new Map()
    this._saveTimer = null
  }

  async init() {
    if (!this._file) return
    try {
      const raw = await readFile(this._file, 'utf-8')
      const data = JSON.parse(raw)
      const now = Date.now()
      for (const [token, row] of Object.entries(data.tokens || {})) {
        if (!row || !row.empNo || !row.exp || row.exp <= now) continue
        this._byToken.set(token, {
          empNo: String(row.empNo),
          kind: String(row.kind || 'fallback'),
          exp: Number(row.exp),
          ssoToken: row.ssoToken ? String(row.ssoToken) : undefined,
        })
      }
    } catch (err) {
      if (err?.code !== 'ENOENT') {
        console.warn('[uds-auth:SessionBridge] load failed:', err.message)
      }
    }
  }

  _scheduleSave() {
    if (!this._file || this._saveTimer) return
    this._saveTimer = setTimeout(() => {
      this._saveTimer = null
      void this._persist()
    }, 200)
  }

  async _persist() {
    if (!this._file) return
    const now = Date.now()
    const tokens = {}
    for (const [token, row] of this._byToken) {
      if (row.exp <= now) {
        this._byToken.delete(token)
        continue
      }
      // Persist bridge metadata only — strip upstream SSO token from disk (SEC-17).
      tokens[token] = {
        empNo: row.empNo,
        kind: row.kind,
        exp: row.exp,
      }
    }
    try {
      await atomicWriteJson(this._file, { tokens }, { mode: 0o600 })
    } catch (err) {
      console.warn('[uds-auth:SessionBridge] save failed:', err.message)
    }
  }

  /**
   * @param {{ empNo: string, kind?: string, ssoToken?: string, ttlMs?: number, token?: string }} row
   * @returns {{ empNo: string, kind: string, token: string, exp: number }}
   */
  mint(row) {
    const empNo = String(row.empNo || '').trim()
    if (!empNo) throw new Error('bridge_empNo_required')
    const kind = String(row.kind || 'fallback')
    // Prefer caller-supplied token (local session bearer) so bridge ≡ session proof.
    const token = row.token ? String(row.token) : randomBytes(32).toString('hex')
    if (token.length < 32) throw new Error('bridge_token_too_short')
    const exp = Date.now() + (row.ttlMs || this._ttlMs)
    this._byToken.set(token, {
      empNo,
      kind,
      exp,
      ssoToken: row.ssoToken ? String(row.ssoToken) : undefined,
    })
    this._scheduleSave()
    return { empNo, kind, token, exp }
  }

  /**
   * @param {string} empNo
   * @param {string} token
   * @returns {{ empNo: string, kind: string, ssoToken?: string } | null}
   */
  verify(empNo, token) {
    const t = String(token || '').trim()
    const e = String(empNo || '').trim()
    if (!t || !e) return null
    const row = this._byToken.get(t)
    if (!row) return null
    if (row.exp <= Date.now()) {
      this._byToken.delete(t)
      this._scheduleSave()
      return null
    }
    if (!safeEqualStr(row.empNo, e)) return null
    return { empNo: row.empNo, kind: row.kind, ssoToken: row.ssoToken }
  }

  /**
   * Slide bridge expiry with its local session (bridge token ≡ session bearer).
   * Without this the bridge died at mint+TTL even while the session stayed active,
   * leaving cookie-less Desktop (and emergency admins, who have no portal SSO
   * re-mint path) anonymous on remote.mux.
   * @param {string} token
   * @param {number} [ttlMs]
   * @returns {boolean}
   */
  touch(token, ttlMs) {
    const t = String(token || '').trim()
    if (!t) return false
    const row = this._byToken.get(t)
    if (!row) return false
    const now = Date.now()
    if (row.exp <= now) {
      this._byToken.delete(t)
      this._scheduleSave()
      return false
    }
    const next = now + (Number(ttlMs) > 0 ? Number(ttlMs) : this._ttlMs)
    if (next <= row.exp) return true
    row.exp = next
    this._scheduleSave()
    return true
  }

  /**
   * Slide every live bridge of an empNo. Used when activity arrives over the WS mux,
   * where only the sessionId (not the bearer) is known. Safe: a bridge only carries
   * the bearer — the session store still decides whether it authenticates.
   * @param {string} empNo
   * @param {number} [ttlMs]
   */
  touchEmpNo(empNo, ttlMs) {
    const e = String(empNo || '').trim()
    if (!e) return
    for (const [token, row] of this._byToken) {
      if (row.empNo === e) this.touch(token, ttlMs)
    }
  }

  /** Clear all bridge tokens for an empNo (logout). */
  revokeEmpNo(empNo) {
    const e = String(empNo || '').trim()
    if (!e) return
    let changed = false
    for (const [token, row] of this._byToken) {
      if (row.empNo === e) {
        this._byToken.delete(token)
        changed = true
      }
    }
    if (changed) this._scheduleSave()
  }

  /**
   * D04: revoke only bridges whose kind matches (password vs sealed_box).
   * @param {string} empNo
   * @param {string|string[]} kinds
   */
  revokeEmpNoKinds(empNo, kinds) {
    const e = String(empNo || '').trim()
    const allow = new Set(Array.isArray(kinds) ? kinds.map(String) : [String(kinds)])
    if (!e || !allow.size) return 0
    let n = 0
    for (const [token, row] of this._byToken) {
      if (row.empNo === e && allow.has(String(row.kind || 'fallback'))) {
        this._byToken.delete(token)
        n++
      }
    }
    if (n) this._scheduleSave()
    return n
  }

  revokeToken(token) {
    const t = String(token || '').trim()
    if (!t) return
    if (this._byToken.delete(t)) this._scheduleSave()
  }

  /**
   * T01: short-TTL, single-use WS handshake ticket (not a reusable session bearer).
   * @param {{ empNo: string, bearer: string, ttlMs?: number }} input
   */
  mintWsTicket(input) {
    const empNo = String(input?.empNo || '').trim()
    const bearer = String(input?.bearer || '').trim()
    if (!empNo || bearer.length < 16) throw new Error('ws_ticket_input_required')
    const now = Date.now()
    for (const [k, v] of this._wsTickets) if (v.exp <= now) this._wsTickets.delete(k)
    if (this._wsTickets.size >= 5000) throw new Error('ws_ticket_capacity')
    const ttl = Math.min(120_000, Math.max(15_000, Number(input.ttlMs) || 60_000))
    const ticket = randomBytes(24).toString('hex')
    const exp = Date.now() + ttl
    this._wsTickets.set(ticket, { empNo, bearer, exp })
    return { ticket, empNo, expiresAt: exp, expiresIn: Math.floor(ttl / 1000) }
  }

  /**
   * Atomically consume a WS ticket. Replay returns null.
   * @returns {{ empNo: string, bearer: string } | null}
   */
  consumeWsTicket(ticket) {
    const id = String(ticket || '').trim()
    if (!id) return null
    const row = this._wsTickets.get(id)
    if (!row) return null
    this._wsTickets.delete(id)
    if (row.exp <= Date.now()) return null
    return { empNo: row.empNo, bearer: row.bearer }
  }
}

/**
 * Read bridge credentials from request headers.
 * @param {any} req
 * @returns {{ empNo: string, token: string, kind: string } | null}
 */
export function readBridgeHeaders(req) {
  const headers = req?.headers || {}
  const empNo = String(headers[BRIDGE_EMPNO_HEADER] || '').trim()
  const token = String(headers[BRIDGE_TOKEN_HEADER] || '').trim()
  const kind = String(headers[BRIDGE_KIND_HEADER] || 'fallback').trim() || 'fallback'
  if (!empNo || !token) return null
  return { empNo, token, kind }
}

/**
 * Headers only for reusable bridge credentials.
 * T01: WS upgrade must use one-time `udsWsTicket` (see extractSessionBearer) —
 * long-lived bridge tokens in the URL query are ignored.
 * @param {any} req
 * @returns {{ empNo: string, token: string, kind: string } | null}
 */
export function readBridgeFromRequest(req) {
  return readBridgeHeaders(req)
}

/**
 * Read one-time WS ticket id from upgrade URL (does not consume).
 * @param {any} req
 * @returns {string|null}
 */
export function readWsTicketFromRequest(req) {
  try {
    const url = new URL(req?.url || '/', 'http://uds-auth.local')
    return String(url.searchParams.get('udsWsTicket') || '').trim() || null
  } catch {
    return null
  }
}
