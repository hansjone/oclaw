/**
 * Outbound HTTP(S) that must NOT use HTTP_PROXY / HTTPS_PROXY.
 * ZTE icenter / UAC user APIs are intranet-only; corporate forward proxies
 * typically return 401/403 and never reach the real service.
 *
 * SEC-16: subject must strictly equal requested empNo — no substring / digit-contains match.
 */
import http from 'node:http'
import https from 'node:https'

const MAX_RESPONSE_BYTES = 2 * 1024 * 1024

/**
 * @param {string|URL} url
 * @param {{ method?: string, headers?: Record<string,string|number>, body?: string|Buffer, timeoutMs?: number, maxBytes?: number }} opts
 * @returns {Promise<{ statusCode: number, headers: object, body: string, json: any }>}
 */
export function directRequest(url, opts = {}) {
  const target = typeof url === 'string' ? new URL(url) : url
  const isHttps = target.protocol === 'https:'
  const lib = isHttps ? https : http
  const method = (opts.method || 'GET').toUpperCase()
  const body = opts.body == null ? null : Buffer.isBuffer(opts.body) ? opts.body : Buffer.from(String(opts.body))
  const headers = { ...(opts.headers || {}) }
  if (body && headers['Content-Length'] == null && headers['content-length'] == null) {
    headers['Content-Length'] = body.length
  }
  const timeoutMs = Math.min(Math.max(Number(opts.timeoutMs) || 3000, 500), 60000)
  const maxBytes = opts.maxBytes ?? MAX_RESPONSE_BYTES

  // Fresh Agent — never inherit globalAgent (often patched by proxy bootstraps).
  const agent = new lib.Agent({ keepAlive: false })

  return new Promise((resolve, reject) => {
    const req = lib.request({
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || (isHttps ? 443 : 80),
      path: target.pathname + target.search,
      method,
      headers,
      agent,
      timeout: timeoutMs,
    }, (res) => {
      const chunks = []
      let total = 0
      res.on('data', (c) => {
        total += c.length
        if (total > maxBytes) {
          req.destroy()
          reject(new Error(`directRequest response too large (>${maxBytes})`))
          return
        }
        chunks.push(c)
      })
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8')
        let json = null
        try { json = JSON.parse(text) } catch { json = null }
        resolve({
          statusCode: res.statusCode || 0,
          headers: res.headers,
          body: text,
          json,
        })
      })
    })
    req.on('error', reject)
    req.on('timeout', () => {
      req.destroy()
      reject(new Error(`directRequest timeout after ${timeoutMs}ms: ${target.host}`))
    })
    if (body) req.write(body)
    req.end()
  })
}

function extractSubject(row) {
  if (!row || typeof row !== 'object') return ''
  return String(
    row.employeeShortId || row.employeeNO || row.empUIID || row.empNo || '',
  ).trim()
}

function subjectsEqual(a, b) {
  return String(a || '').trim() === String(b || '').trim()
}

/**
 * POST userSearchUrl with X-Emp-No + X-Auth-Value (intranet, no proxy).
 * Success requires: HTTP 2xx, business success code, exactly one subject-matching row.
 */
export async function searchUserByEmpNoToken({
  userSearchUrl,
  empNo,
  token,
  empNoHeader = 'X-Emp-No',
  authValueHeader = 'X-Auth-Value',
  origin,
  timeoutMs = 3000,
}) {
  if (!userSearchUrl || !empNo || !token) {
    return { ok: false, reason: 'missing_args' }
  }
  const want = String(empNo).trim()
  const body = JSON.stringify({
    employeeShortId: want,
    enableLabel: true,
    keyword: want,
  })
  const headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    [empNoHeader]: want,
    [authValueHeader]: token,
  }
  if (origin) {
    headers.Origin = origin
    headers.Referer = String(origin).replace(/\/?$/, '/')
  }

  let res
  try {
    res = await directRequest(userSearchUrl, { method: 'POST', headers, body, timeoutMs })
  } catch (err) {
    let host = ''
    try { host = new URL(userSearchUrl).hostname } catch { /* diagnostics only */ }
    return { ok: false, reason: 'network', error: err.message, code: err.code, host }
  }

  // Only accept 2xx — do not treat HTTP 500 + biz success as ok (SEC-16).
  if (res.statusCode < 200 || res.statusCode >= 300) {
    return {
      ok: false,
      reason: res.statusCode === 401 || res.statusCode === 403 ? 'http_auth' : 'http_status',
      statusCode: res.statusCode,
      msg: res.json?.code?.msg || res.json?.msg || res.body.slice(0, 200),
      hint: res.statusCode === 401 || res.statusCode === 403
        ? 'userSearchUrl must be reachable on intranet WITHOUT HTTP(S)_PROXY'
        : undefined,
    }
  }

  const result = res.json
  if (!result || typeof result !== 'object') {
    return { ok: false, reason: 'bad_json', statusCode: res.statusCode, raw: res.body.slice(0, 300) }
  }

  const code = result?.code?.code ?? result?.code
  if (code !== '0000' && code !== 0 && code !== '0') {
    return {
      ok: false,
      reason: 'biz_code',
      statusCode: res.statusCode,
      code,
      msg: result?.code?.msg || result?.msg,
    }
  }

  const list = Array.isArray(result?.bo) ? result.bo
    : Array.isArray(result?.bo?.rows) ? result.bo.rows
      : Array.isArray(result?.bo?.list) ? result.bo.list
        : []
  if (!list.length) {
    return { ok: false, reason: 'empty', statusCode: res.statusCode }
  }

  // Strict subject equality — no substring / digit-contains (SEC-16).
  const matches = list.filter((row) => subjectsEqual(extractSubject(row), want))
  if (matches.length !== 1) {
    return {
      ok: false,
      reason: matches.length === 0 ? 'emp_mismatch' : 'ambiguous',
      statusCode: res.statusCode,
      matchCount: matches.length,
    }
  }

  const emp = matches[0]
  const subject = extractSubject(emp)
  if (!subject || !subjectsEqual(subject, want)) {
    return { ok: false, reason: 'emp_mismatch', resolvedEmpNo: subject }
  }
  // Reserved / emergency account names never come from UAC search.
  if (subject === 'administrator' || subject.startsWith('__')) {
    return { ok: false, reason: 'reserved_subject' }
  }

  return {
    ok: true,
    profile: {
      empNo: subject,
      username: emp.name || emp.empName || emp.userName || subject,
      department: emp.deptFullName || emp.deptName || emp.deptShortName || emp.orgNamePath || emp.orgName || emp.department || '',
      organization: emp.orgNamePath || emp.orgName || '',
      email: emp.email || emp.mail || '',
      phone: emp.mobile || emp.phone || '',
      // Omit raw upstream blob from default profile to limit accidental logging.
      token: undefined,
    },
    result: { code: result.code },
  }
}
