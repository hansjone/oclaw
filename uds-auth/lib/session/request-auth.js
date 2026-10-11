/**
 * Extract local session bearer from Cookie / Header / Desktop bridge.
 * EmpNo cookies (PORTALSSO*, UDS_FALLBACK_*) are never auth proofs.
 */
import { SESSION_COOKIE, SESSION_HEADER } from './store.js'
import { readBridgeFromRequest, readWsTicketFromRequest } from '../session-bridge.js'
import { requestIsLoopback } from '../skill-credentials.js'

function parseCookie(header, name) {
  if (!header || typeof header !== 'string') return null
  for (const part of header.split(';')) {
    const idx = part.indexOf('=')
    if (idx < 0) continue
    if (part.slice(0, idx).trim() !== name) continue
    try {
      return decodeURIComponent(part.slice(idx + 1).trim())
    } catch {
      return part.slice(idx + 1).trim()
    }
  }
  return null
}

/**
 * @param {any} req
 * @param {{ sessionBridge?: any, isLiveBearer?: (bearer: string) => boolean }} [deps]
 *   isLiveBearer: when given, a cookie bearer with no live session no longer shadows
 *   a valid WS ticket / bridge (stale UDS_SESSION → anonymous remote.mux).
 * @returns {{ bearer: string, via: 'cookie'|'header'|'bridge', bridgeEmpNo?: string } | null}
 */
export function extractSessionBearer(req, deps = {}) {
  const headers = req?.headers || {}
  const fromHeader = String(headers[SESSION_HEADER] || headers['X-UDS-Session'] || '').trim()
  if (fromHeader) return { bearer: fromHeader, via: 'header' }

  const fromCookie = parseCookie(headers.cookie || '', SESSION_COOKIE)
  if (fromCookie) {
    const cookieHit = { bearer: fromCookie, via: 'cookie' }
    if (typeof deps.isLiveBearer !== 'function') return cookieHit
    let live = false
    try { live = !!deps.isLiveBearer(fromCookie) } catch { live = false }
    if (live) return cookieHit
    return extractBridgeBearer(req, deps) || cookieHit
  }
  return extractBridgeBearer(req, deps)
}

/**
 * Async variant for stores that can only read sessions asynchronously (Redis).
 * @param {any} req
 * @param {{ sessionBridge?: any, isLiveBearer?: (bearer: string) => Promise<boolean>|boolean }} [deps]
 */
export async function extractSessionBearerAsync(req, deps = {}) {
  const headers = req?.headers || {}
  const fromHeader = String(headers[SESSION_HEADER] || headers['X-UDS-Session'] || '').trim()
  if (fromHeader) return { bearer: fromHeader, via: 'header' }

  const fromCookie = parseCookie(headers.cookie || '', SESSION_COOKIE)
  if (fromCookie) {
    const cookieHit = { bearer: fromCookie, via: 'cookie' }
    if (typeof deps.isLiveBearer !== 'function') return cookieHit
    let live = false
    try { live = !!(await deps.isLiveBearer(fromCookie)) } catch { live = false }
    if (live) return cookieHit
    return extractBridgeBearer(req, deps) || cookieHit
  }
  return extractBridgeBearer(req, deps)
}

/** WS ticket (upgrade only) → loopback bridge query (upgrade only) → bridge headers. */
function extractBridgeBearer(req, deps = {}) {
  const headers = req?.headers || {}
  if (deps.sessionBridge) {
    try {
      // D07/T01: one-time WS ticket only on WebSocket upgrade to remote.mux — never normal HTTP.
      // 0.3.9 accepted Upgrade: websocket alone. 0.3.10 also required Connection to list
      // "upgrade"; some Desktop/Electron stacks omit that and then never consume the ticket
      // → workspace follow stays anonymous →「未分组」. Keep path+method+Upgrade gate.
      const pathname = new URL(req?.url || '/', 'http://uds-auth.local').pathname
      const upgrade = String(headers.upgrade || '').toLowerCase()
      const connection = String(headers.connection || '').toLowerCase()
      const connectionOk = !connection
        || connection.split(',').map((x) => x.trim()).includes('upgrade')
      const isUpgrade = String(req?.method || 'GET').toUpperCase() === 'GET'
        && upgrade === 'websocket'
        && connectionOk
        && pathname === '/api/remote.mux'
      const wsTicket = isUpgrade ? readWsTicketFromRequest(req) : null
      if (wsTicket && typeof deps.sessionBridge.consumeWsTicket === 'function') {
        const consumed = deps.sessionBridge.consumeWsTicket(wsTicket)
        if (consumed?.bearer) {
          return {
            bearer: consumed.bearer,
            via: 'ws_ticket',
            bridgeEmpNo: consumed.empNo,
          }
        }
      }
      // Desktop 0.3.9 fallback: loopback remote.mux may carry bridge in the query
      // when one-time ticket mint fails (sync XHR/CORS). Not accepted off-loopback.
      if (isUpgrade && requestIsLoopback(req)) {
        try {
          const q = new URL(req?.url || '/', 'http://uds-auth.local').searchParams
          const empNo = String(q.get('udsBridgeEmpNo') || '').trim()
          const token = String(q.get('udsBridgeToken') || '').trim()
          if (empNo && token && typeof deps.sessionBridge.verify === 'function') {
            const ok = deps.sessionBridge.verify(empNo, token)
            if (ok) {
              return { bearer: token, via: 'bridge_query', bridgeEmpNo: ok.empNo }
            }
          }
        } catch { /* ignore */ }
      }
      const hdr = readBridgeFromRequest(req)
      if (hdr?.token) {
        const ok = deps.sessionBridge.verify(hdr.empNo, hdr.token)
        if (ok) {
          // Bridge token itself is the local bearer (minted at login). Headers only.
          return { bearer: hdr.token, via: 'bridge', bridgeEmpNo: ok.empNo }
        }
      }
    } catch { /* ignore */ }
  }
  return null
}

/**
 * Portal SSO cookies for login exchange only — not sufficient for principal.
 */
export function extractPortalCredentials(req) {
  const cookie = req?.headers?.cookie || ''
  const empNo = parseCookie(cookie, 'PORTALSSOUser')
    || parseCookie(cookie, 'ZTEDPGSSOUser')
  const token = parseCookie(cookie, 'PORTALSSOCookie')
    || parseCookie(cookie, 'ZTEDPGSSOCookie')
  if (!empNo || !token) return null
  return { empNo: String(empNo), token: String(token) }
}

/** Display hint only — never authenticate. */
export function extractDisplayEmpNoHint(req) {
  const cookie = req?.headers?.cookie || ''
  return parseCookie(cookie, 'UDS_FALLBACK_UI')
    || parseCookie(cookie, 'UDS_FALLBACK_USER')
    || parseCookie(cookie, 'PORTALSSOUser')
    || parseCookie(cookie, 'ZTEDPGSSOUser')
    || null
}

export function buildSessionCookie(bearer, maxAgeSeconds, { secure = false } = {}) {
  const parts = [
    `${SESSION_COOKIE}=${encodeURIComponent(bearer)}`,
    `Max-Age=${Math.max(60, Number(maxAgeSeconds) || 1800)}`,
    'Path=/',
    'HttpOnly',
    'SameSite=Lax',
  ]
  if (secure) parts.push('Secure')
  return parts.join('; ')
}

export function clearSessionCookie({ secure = false } = {}) {
  const base = `${SESSION_COOKIE}=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax`
  return secure ? `${base}; Secure` : base
}

export { SESSION_COOKIE, SESSION_HEADER, parseCookie }
