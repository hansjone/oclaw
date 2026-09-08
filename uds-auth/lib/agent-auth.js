/**
 * Loopback agent APIs: credentials + outbound proxy.
 */
import { directRequest } from './uds/user-search.js'
import { requestIsLoopback } from './skill-credentials.js'

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
  let raw = ''
  for await (const chunk of req) raw += chunk
  if (!raw) return {}
  try { return JSON.parse(raw) } catch { return {} }
}

/**
 * @param {{
 *   resolveCredentialsForSession: (sessionId: string) => Promise<{empNo:string,token:string}|null>,
 *   resolveCredentialsForEmpNo: (empNo: string) => Promise<{empNo:string,token:string}|null>,
 *   empNoHeader?: string,
 *   authValueHeader?: string,
 *   outboundHosts?: string[],
 * }} deps
 */
export function createAgentAuthHandlers(deps) {
  const empNoHeader = deps.empNoHeader || 'X-Emp-No'
  const authValueHeader = deps.authValueHeader || 'X-Auth-Value'

  function allowedHosts() {
    const list = typeof deps.outboundHosts === 'function'
      ? deps.outboundHosts()
      : deps.outboundHosts
    if (Array.isArray(list) && list.length) return list.map(String)
    return DEFAULT_OUTBOUND_HOSTS.slice()
  }

  function hostAllowed(hostname) {
    const host = String(hostname || '').toLowerCase()
    return allowedHosts().some((h) => host === h.toLowerCase() || host.endsWith('.' + h.toLowerCase()))
  }

  async function resolveFromRequest(req, body = {}) {
    const sessionId = readSessionId(req, body)
    if (sessionId) {
      const creds = await deps.resolveCredentialsForSession(String(sessionId))
      if (creds) return { creds, sessionId: String(sessionId) }
    }
    const empNo = body.empNo || req.headers['x-uds-emp-no']
    if (empNo) {
      const creds = await deps.resolveCredentialsForEmpNo(String(empNo))
      if (creds) return { creds, sessionId: sessionId ? String(sessionId) : null }
    }
    return { creds: null, sessionId: sessionId ? String(sessionId) : null }
  }

  async function handleAgentCredentials(req, res) {
    if (!requestIsLoopback(req)) {
      return sendJSON(res, 403, { error: 'agent-credentials is loopback-only' })
    }
    const method = (req.method || 'GET').toUpperCase()
    if (method !== 'GET' && method !== 'POST') {
      return sendJSON(res, 405, { error: 'Method not allowed' })
    }
    const body = method === 'POST' ? await readJsonBody(req) : {}
    const { creds, sessionId } = await resolveFromRequest(req, body)
    if (!creds) {
      return sendJSON(res, 401, {
        error: 'no_skill_credentials',
        message: '请先完成 UDS 扫码登录',
        sessionId: sessionId || null,
      })
    }
    return sendJSON(res, 200, {
      empNo: creds.empNo,
      token: creds.token,
      updatedAt: creds.updatedAt || null,
    })
  }

  async function handleOutbound(req, res) {
    if (!requestIsLoopback(req)) {
      return sendJSON(res, 403, { error: 'outbound is loopback-only' })
    }
    const method = (req.method || 'POST').toUpperCase()
    if (method !== 'POST') {
      return sendJSON(res, 405, { error: 'Method not allowed' })
    }
    const body = await readJsonBody(req)
    const { creds } = await resolveFromRequest(req, body)
    if (!creds) {
      return sendJSON(res, 401, {
        error: 'no_skill_credentials',
        message: '请先完成 UDS 扫码登录',
      })
    }

    const targetUrl = body.url
    if (!targetUrl || typeof targetUrl !== 'string') {
      return sendJSON(res, 400, { error: 'url required' })
    }
    let parsed
    try {
      parsed = new URL(targetUrl)
    } catch {
      return sendJSON(res, 400, { error: 'invalid url' })
    }
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
      return sendJSON(res, 400, { error: 'unsupported protocol' })
    }
    if (!hostAllowed(parsed.hostname)) {
      return sendJSON(res, 403, { error: 'host_not_allowed', host: parsed.hostname })
    }

    const upstreamMethod = String(body.method || 'POST').toUpperCase()
    const headers = { ...(body.headers && typeof body.headers === 'object' ? body.headers : {}) }
    for (const k of Object.keys(headers)) {
      const lower = k.toLowerCase()
      if (lower === 'x-auth-value' || lower === 'x-emp-no' || lower === 'host' || lower === 'content-length') {
        delete headers[k]
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
        timeoutMs: Number(body.timeoutMs) || 30000,
      })
      res.statusCode = out.statusCode || 502
      res.setHeader('Content-Type', 'application/json; charset=utf-8')
      res.setHeader('Cache-Control', 'no-store')
      res.setHeader('X-Uds-Outbound-Status', String(out.statusCode || 0))
      // Wrap so skill gets status + body without leaking injected auth headers
      res.end(JSON.stringify({
        statusCode: out.statusCode,
        headers: sanitizeUpstreamHeaders(out.headers),
        body: out.body,
        json: out.json,
      }))
    } catch (err) {
      return sendJSON(res, 502, { error: 'upstream_failed', message: err.message || String(err) })
    }
  }

  return { handleAgentCredentials, handleOutbound, DEFAULT_OUTBOUND_HOSTS }
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
