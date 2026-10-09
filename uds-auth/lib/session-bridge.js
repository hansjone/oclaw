/**
 * Cookie-less session bridge for Desktop (dsh-app:// drops Set-Cookie / document.cookie).
 *
 * Login handlers mint a random token; the browser stores { empNo, token, kind } in
 * localStorage and sends X-UDS-Bridge-* headers on subsequent /uds-auth requests.
 */
import { randomBytes, timingSafeEqual, createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname } from 'node:path'

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
      tokens[token] = {
        empNo: row.empNo,
        kind: row.kind,
        exp: row.exp,
        ...(row.ssoToken ? { ssoToken: row.ssoToken } : {}),
      }
    }
    try {
      await mkdir(dirname(this._file), { recursive: true })
      await writeFile(this._file, JSON.stringify({ tokens }, null, 2), 'utf-8')
    } catch (err) {
      console.warn('[uds-auth:SessionBridge] save failed:', err.message)
    }
  }

  /**
   * @param {{ empNo: string, kind?: string, ssoToken?: string, ttlMs?: number }} row
   * @returns {{ empNo: string, kind: string, token: string, exp: number }}
   */
  mint(row) {
    const empNo = String(row.empNo || '').trim()
    if (!empNo) throw new Error('bridge_empNo_required')
    const kind = String(row.kind || 'fallback')
    const token = randomBytes(32).toString('hex')
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

  revokeToken(token) {
    const t = String(token || '').trim()
    if (!t) return
    if (this._byToken.delete(t)) this._scheduleSave()
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
 * Headers first, then WebSocket upgrade query
 * (`?udsBridgeEmpNo=&udsBridgeToken=&udsBridgeKind=`).
 * Browser WS cannot set custom headers; Desktop also drops cookies.
 * @param {any} req
 * @returns {{ empNo: string, token: string, kind: string } | null}
 */
export function readBridgeFromRequest(req) {
  const fromHdr = readBridgeHeaders(req)
  if (fromHdr) return fromHdr
  try {
    const url = new URL(req?.url || '/', 'http://uds-auth.local')
    const empNo = String(
      url.searchParams.get('udsBridgeEmpNo')
      || url.searchParams.get('x-uds-bridge-empno')
      || '',
    ).trim()
    const token = String(
      url.searchParams.get('udsBridgeToken')
      || url.searchParams.get('x-uds-bridge-token')
      || '',
    ).trim()
    const kind = String(
      url.searchParams.get('udsBridgeKind')
      || url.searchParams.get('x-uds-bridge-kind')
      || 'fallback',
    ).trim() || 'fallback'
    if (!empNo || !token) return null
    return { empNo, token, kind }
  } catch {
    return null
  }
}
