/**
 * Loopback agent APIs: credentials + outbound proxy.
 * SEC-05: no XFF trust; no arbitrary empNo credential fetch.
 * Caller must prove a local session bearer whose empNo owns the DSH sessionId
 * (or matches an explicit capability in a later phase).
 */
import { directRequest } from './uds/user-search.js'
import { requestIsLoopback } from './skill-credentials.js'
import { apiError, resolveLocale } from './i18n.js'
import { extractSessionBearer } from './session/request-auth.js'
import { readJsonBodyLimited, DEFAULT_MAX_BODY } from './utils/read-body.js'
import { audit } from './utils/audit-log.js'

const DEFAULT_OUTBOUND_HOSTS = [
  'icenterapi.zte.com.cn',
  'icentermsg.dt.zte.com.cn',
]

function sendJSON(res, code, data) {
  res.statusCode = code >= 200 && code < 300 ? 200 : code
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store')
  res.end(JSON.stringify(data))
}

function sendErr(req, res, status, code, vars) {
  return sendJSON(res, status, apiError(code, resolveLocale(req), vars))
}

function readSessionId(req, body) {
  const h = req.headers || {}
  return (
    h['x-dsh-session-id']
    || h['X-DSH-Session-Id']
    || body?.sessionId
    || body?.dshSessionId
    || null
  )
}

async function readJsonBody(req) {
  try {
    return await readJsonBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
  } catch (err) {
    if (err?.code === 'payload_too_large' || err?.code === 'invalid_json') throw err
    return {}
  }
}

/**
 * @param {{
 *   resolveCredentialsForSession: (sessionId: string) => Promise<{empNo:string,token:string}|null>,
 *   resolveCallerSession: (req: any) => Promise<{empNo:string,sessionId?:string}|null>,
 *   getSessionOwner: (sessionId: string) => string|null,
 *   empNoHeader?: string,
 *   authValueHeader?: string,
 *   outboundHosts?: string[],
 *   sessionBridge?: any,
 *   allowRawTokenResponse?: boolean|(() => boolean),
 *   taskCapabilities?: import('./task-capability.js').TaskCapabilityStore,
 * }} deps
 */
export function createAgentAuthHandlers(deps) {
  const empNoHeader = deps.empNoHeader || 'X-Emp-No'
  const authValueHeader = deps.authValueHeader || 'X-Auth-Value'

  /** R05: live flag — closing allowRawAgentToken must take effect without restart. */
  function allowRawToken() {
    if (typeof deps.allowRawTokenResponse === 'function') {
      return deps.allowRawTokenResponse() === true
    }
    return deps.allowRawTokenResponse === true
  }

  function allowedHosts() {
    const list = typeof deps.outboundHosts === 'function'
      ? deps.outboundHosts()
      : deps.outboundHosts
    // Empty whitelist = deny all (SEC-18); do not fall back to defaults when explicitly [].
    if (Array.isArray(list)) return list.map(String).map((s) => s.trim().toLowerCase()).filter(Boolean)
    // Explicit empty string also denies all; only undefined/null uses packaged defaults.
    if (list === '') return []
    if (list == null) return DEFAULT_OUTBOUND_HOSTS.map((s) => s.toLowerCase())
    return String(list).split(/[,;\s]+/).map((s) => s.trim().toLowerCase()).filter(Boolean)
  }

  /** Exact hostname match only — no automatic subdomain wildcard (SEC-18). */
  function hostAllowed(hostname) {
    const host = String(hostname || '').toLowerCase()
    if (!host) return false
    const list = allowedHosts()
    if (!list.length) return false
    return list.includes(host)
  }

  async function resolveCaller(req, body = {}) {
    // R06: task capability (skill/cron) — preferred over requiring a browser session.
    const caps = deps.taskCapabilities
    if (caps) {
      const raw = caps.extractFromRequest?.(req)
        || body?.taskCapability
        || body?.capability
        || null
      if (raw) {
        const sessionId = readSessionId(req, body)
        const verified = caps.verify(raw, {
          audience: 'uds-auth-agent',
          dshSessionId: sessionId || undefined,
        })
        if (verified?.empNo) {
          return {
            empNo: verified.empNo,
            sessionId: verified.dshSessionId || sessionId || undefined,
            via: 'task_capability',
            capabilityId: verified.id,
            scopes: verified.scopes,
          }
        }
        return null
      }
    }
    if (typeof deps.resolveCallerSession === 'function') {
      return deps.resolveCallerSession(req)
    }
    return null
  }

  /**
   * Authorize: loopback + (local session bearer OR task capability)
   * + sessionId owned by caller. body.empNo is ignored as an auth input.
   * @param {string} [requiredScope] A06: exact scope for the endpoint ('credentials'|'outbound')
   */
  async function resolveAuthorizedCreds(req, body = {}, requiredScope) {
    const caller = await resolveCaller(req, body)
    if (!caller?.empNo) return { error: 'caller_unauthenticated', creds: null, sessionId: null }

    const sessionId = readSessionId(req, body)
    if (!sessionId) {
      return { error: 'session_id_required', creds: null, sessionId: null }
    }

    const owner = deps.getSessionOwner?.(String(sessionId)) || null
    if (!owner || String(owner) !== String(caller.empNo)) {
      return { error: 'session_owner_mismatch', creds: null, sessionId: String(sessionId) }
    }

    // A06: credentials vs outbound require their own scope — not either-or.
    if (caller.via === 'task_capability' && requiredScope) {
      if (!Array.isArray(caller.scopes) || !caller.scopes.includes(requiredScope)) {
        return { error: 'capability_scope_denied', creds: null, sessionId: String(sessionId) }
      }
    }

    // Live account check when roles store is wired.
    if (typeof deps.isAccountActive === 'function' && !deps.isAccountActive(caller.empNo)) {
      return { error: 'account_disabled', creds: null, sessionId: String(sessionId) }
    }

    const creds = await deps.resolveCredentialsForSession(String(sessionId))
    if (!creds || String(creds.empNo) !== String(caller.empNo)) {
      // Credentials follow the session OWNER (stamped at creation), not whoever scanned last.
      // Emergency / local-admin owners never hold UAC credentials, so name the owner.
      const owner = String(caller.empNo)
      const noUac = owner === 'administrator' || owner.startsWith('__')
      return {
        error: noUac ? 'session_owner_no_uac' : 'no_skill_credentials',
        vars: { owner },
        creds: null,
        sessionId: String(sessionId),
      }
    }
    return { error: null, creds, sessionId: String(sessionId), caller }
  }

  async function handleAgentCredentials(req, res) {
    if (!requestIsLoopback(req)) {
      audit({ action: 'agent_credentials', decision: 'deny', reasonCode: 'loopback_only' })
      return sendErr(req, res, 403, 'loopback_only_credentials')
    }
    if (!allowRawToken()) {
      audit({ action: 'agent_credentials', decision: 'deny', reasonCode: 'raw_token_disabled' })
      return sendJSON(res, 403, {
        ...apiError('raw_token_disabled', resolveLocale(req)),
        hint: 'use /uds-auth/api/agent-outbound with a verified local session',
      })
    }
    const method = (req.method || 'GET').toUpperCase()
    if (method !== 'GET' && method !== 'POST') {
      return sendErr(req, res, 405, 'method_not_allowed')
    }
    let body = {}
    try {
      body = method === 'POST' ? await readJsonBody(req) : {}
    } catch (err) {
      return sendErr(req, res, err.statusCode || 400, err.code || 'invalid_json')
    }
    const { error, creds, sessionId, vars } = await resolveAuthorizedCreds(req, body, 'credentials')
    if (error || !creds) {
      audit({
        action: 'agent_credentials',
        decision: 'deny',
        reasonCode: error || 'no_skill_credentials',
        meta: { sessionId },
      })
      return sendJSON(res, 401, {
        ...apiError(error || 'no_skill_credentials', resolveLocale(req), vars),
        sessionId: sessionId || null,
      })
    }
    audit({
      action: 'agent_credentials',
      decision: 'allow',
      actor: creds.empNo,
      resource: sessionId,
    })
    return sendJSON(res, 200, {
      empNo: creds.empNo,
      token: creds.token,
      updatedAt: creds.updatedAt || null,
    })
  }

  async function handleOutbound(req, res) {
    if (!requestIsLoopback(req)) {
      return sendErr(req, res, 403, 'loopback_only_outbound')
    }
    const method = (req.method || 'POST').toUpperCase()
    if (method !== 'POST') {
      return sendErr(req, res, 405, 'method_not_allowed')
    }
    const body = await readJsonBody(req)
    const { error, creds, vars, sessionId } = await resolveAuthorizedCreds(req, body, 'outbound')
    if (error || !creds) {
      audit({
        action: 'agent_outbound',
        decision: 'deny',
        reasonCode: error || 'no_skill_credentials',
        meta: { sessionId, owner: vars?.owner },
      })
      return sendErr(req, res, 401, error || 'no_skill_credentials', vars)
    }

    const targetUrl = body.url
    if (!targetUrl || typeof targetUrl !== 'string') {
      return sendErr(req, res, 400, 'url_required')
    }
    let parsed
    try {
      parsed = new URL(targetUrl)
    } catch {
      return sendErr(req, res, 400, 'invalid_url')
    }
    // Credentials must never travel over cleartext HTTP (SEC-18).
    if (parsed.protocol !== 'https:') {
      return sendErr(req, res, 400, 'https_required')
    }
    if (parsed.username || parsed.password) {
      return sendErr(req, res, 400, 'invalid_url')
    }
    if (!hostAllowed(parsed.hostname)) {
      return sendJSON(res, 403, apiError('host_not_allowed', resolveLocale(req), { host: parsed.hostname }))
    }

    const upstreamMethod = String(body.method || 'POST').toUpperCase()
    if (!['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'].includes(upstreamMethod)) {
      return sendErr(req, res, 400, 'method_not_allowed')
    }
    // Rebuild headers from whitelist only — never forward caller Authorization/Cookie.
    const allowedHeaderNames = new Set([
      'content-type', 'accept', 'accept-language', 'x-lang-id', 'x-requested-with',
    ])
    const headers = {}
    if (body.headers && typeof body.headers === 'object') {
      for (const [k, v] of Object.entries(body.headers)) {
        if (allowedHeaderNames.has(String(k).toLowerCase()) && v != null) {
          headers[k] = String(v).slice(0, 1024)
        }
      }
    }
    headers[empNoHeader] = creds.empNo
    headers[authValueHeader] = creds.token
    if (!headers['Content-Type'] && !headers['content-type'] && body.body != null) {
      headers['Content-Type'] = 'application/json;charset=UTF-8'
    }

    let upstreamBody = body.body
    if (upstreamBody != null && typeof upstreamBody !== 'string' && !Buffer.isBuffer(upstreamBody)) {
      upstreamBody = JSON.stringify(upstreamBody)
    }

    try {
      const out = await directRequest(parsed, {
        method: upstreamMethod,
        headers,
        body: upstreamBody,
        timeoutMs: Math.min(Number(body.timeoutMs) || 30000, 60000),
      })
      res.statusCode = out.statusCode || 502
      res.setHeader('Content-Type', 'application/json; charset=utf-8')
      res.setHeader('Cache-Control', 'no-store')
      res.setHeader('X-Uds-Outbound-Status', String(out.statusCode || 0))
      res.end(JSON.stringify({
        statusCode: out.statusCode,
        headers: sanitizeUpstreamHeaders(out.headers),
        body: out.body,
        json: out.json,
      }))
    } catch (err) {
      const payload = apiError('upstream_failed', resolveLocale(req))
      payload.message = payload.message + ': ' + (err.message || String(err))
      return sendJSON(res, 502, payload)
    }
  }

  return { handleAgentCredentials, handleOutbound, DEFAULT_OUTBOUND_HOSTS, extractSessionBearer }
}

function sanitizeUpstreamHeaders(headers) {
  if (!headers || typeof headers !== 'object') return {}
  const out = {}
  for (const [k, v] of Object.entries(headers)) {
    const lower = k.toLowerCase()
    if (lower === 'x-auth-value' || lower.includes('token') || lower.includes('cookie')) continue
    out[k] = v
  }
  return out
}
