/**
 * SEC-19 / R13 / A09: Origin / Host checks for /uds-auth routes.
 * trustedHosts allowlist (exact host[:port]). Empty allowlist = loopback Host only.
 * Desktop (null / missing Origin) allowed only for loopback on mutating methods.
 */
import { requestIsLoopback } from '../skill-credentials.js'

function normalizeHost(h, protocolHint) {
  const lower = String(h || '').toLowerCase()
  if (lower.endsWith(':443') && (protocolHint === 'https:' || !protocolHint)) {
    return lower.slice(0, -4)
  }
  if (lower.endsWith(':80') && (protocolHint === 'http:' || !protocolHint)) {
    return lower.slice(0, -3)
  }
  return lower
}

function hostIsLoopback(host) {
  const raw = String(host || '').trim().toLowerCase()
  // F08: parse bracketed IPv6 authority ([::1]:3000) — do not split on ':'.
  let hostname = raw
  try {
    hostname = new URL('http://' + raw).hostname
  } catch {
    if (raw.startsWith('[')) {
      const end = raw.indexOf(']')
      hostname = end > 0 ? raw.slice(0, end + 1) : raw
    } else {
      hostname = normalizeHost(raw).split(':')[0]
    }
  }
  // Node may return hostname as ::1 or [::1] depending on version.
  const bare = hostname.startsWith('[') && hostname.endsWith(']')
    ? hostname.slice(1, -1)
    : hostname
  return bare === 'localhost' || bare === '127.0.0.1' || bare === '::1'
}

/**
 * @param {import('node:http').IncomingMessage} req
 * @param {{ allowNullOrigin?: boolean, trustedHosts?: string[]|(() => string[]) }} [opts]
 * @returns {{ ok: boolean, reason?: string }}
 */
export function checkRequestOrigin(req, opts = {}) {
  const method = opts.upgrade ? 'POST' : String(req?.method || 'GET').toUpperCase()
  const host = String(req?.headers?.host || '').trim().toLowerCase()
  if (!host) {
    return { ok: false, reason: 'missing_host' }
  }
  if (host.includes('@') || host.includes('\\') || /[\s\0/?#]/.test(host)) {
    return { ok: false, reason: 'invalid_host' }
  }
  try {
    const parsedHost = new URL('http://' + host)
    if (!parsedHost.hostname || parsedHost.username || parsedHost.password || parsedHost.pathname !== '/') {
      return { ok: false, reason: 'invalid_host' }
    }
  } catch { return { ok: false, reason: 'invalid_host' } }

  const trustedRaw = typeof opts.trustedHosts === 'function'
    ? opts.trustedHosts()
    : opts.trustedHosts
  const trusted = Array.isArray(trustedRaw)
    ? trustedRaw.map((h) => normalizeHost(h)).filter(Boolean)
    : []

  const reqHost = normalizeHost(host)
  if (trusted.length) {
    if (!trusted.includes(reqHost)) {
      return { ok: false, reason: 'host_not_trusted' }
    }
  } else if (!hostIsLoopback(host)) {
    // A09: empty trustedHosts = loopback-only default (no silent open allowlist).
    return { ok: false, reason: 'host_not_trusted' }
  }

  if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') {
    return { ok: true }
  }

  const origin = String(req?.headers?.origin || '').trim()
  const fetchSite = String(req?.headers?.['sec-fetch-site'] || '').toLowerCase()

  if (fetchSite === 'cross-site') {
    return { ok: false, reason: 'cross_site' }
  }

  if (!origin || origin === 'null') {
    if (opts.allowNullOrigin !== false && requestIsLoopback(req)) {
      return { ok: true }
    }
    if (!origin && requestIsLoopback(req)) return { ok: true }
    return { ok: false, reason: 'missing_origin' }
  }

  let originUrl
  try {
    originUrl = new URL(origin)
  } catch {
    return { ok: false, reason: 'invalid_origin' }
  }
  // Only the renderer's owned scheme authority may represent Desktop.
  if (originUrl.protocol === 'dsh-app:') {
    return requestIsLoopback(req) && originUrl.hostname === 'app' && !originUrl.port
      && !originUrl.username && !originUrl.password && originUrl.pathname === ''
      ? { ok: true } : { ok: false, reason: 'origin_mismatch' }
  }
  if (!['http:', 'https:'].includes(originUrl.protocol) || originUrl.username || originUrl.password
    || !['', '/'].includes(originUrl.pathname) || originUrl.search || originUrl.hash) {
    return { ok: false, reason: 'invalid_origin' }
  }

  const originHost = normalizeHost(originUrl.host, originUrl.protocol)
  const hostForOrigin = normalizeHost(host, originUrl.protocol)
  if (originHost !== hostForOrigin) {
    return { ok: false, reason: 'origin_mismatch' }
  }
  if (trusted.length && !trusted.includes(originHost)) {
    return { ok: false, reason: 'origin_not_trusted' }
  }
  return { ok: true }
}

/**
 * Reject non-JSON mutating Content-Types for state-changing APIs.
 */
export function requireJsonContentType(req) {
  const method = String(req?.method || 'GET').toUpperCase()
  if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') return { ok: true }
  const ct = String(req?.headers?.['content-type'] || '').toLowerCase()
  if (!ct.includes('application/json')) {
    return { ok: false, reason: 'content_type' }
  }
  return { ok: true }
}
