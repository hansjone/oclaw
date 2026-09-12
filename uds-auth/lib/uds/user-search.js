/**
 * Outbound HTTP(S) that must NOT use HTTP_PROXY / HTTPS_PROXY.
 * ZTE icenter / UAC user APIs are intranet-only; corporate forward proxies
 * typically return 401/403 and never reach the real service.
 */
import http from 'node:http'
import https from 'node:https'

/**
 * @param {string|URL} url
 * @param {{ method?: string, headers?: Record<string,string|number>, body?: string|Buffer, timeoutMs?: number }} opts
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
  const timeoutMs = opts.timeoutMs ?? 3000

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
      res.on('data', (c) => chunks.push(c))
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

/**
 * POST userSearchUrl with X-Emp-No + X-Auth-Value (intranet, no proxy).
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
  const body = JSON.stringify({
    employeeShortId: empNo,
    enableLabel: true,
    keyword: empNo,
  })
  const headers = {
    'Content-Type': 'application/json;charset=UTF-8',
    [empNoHeader]: empNo,
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
    return { ok: false, reason: 'network', error: err.message }
  }

  if (res.statusCode === 401 || res.statusCode === 403) {
    return {
      ok: false,
      reason: 'http_auth',
      statusCode: res.statusCode,
      msg: res.json?.code?.msg || res.json?.msg || res.body.slice(0, 200),
      hint: 'userSearchUrl must be reachable on intranet WITHOUT HTTP(S)_PROXY',
    }
  }

  const result = res.json
  if (!result) {
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
    return { ok: false, reason: 'empty', statusCode: res.statusCode, result }
  }

  const emp = list[0]
  const resolvedEmpNo = String(
    emp.employeeShortId || emp.employeeNO || emp.empUIID || emp.empNo || empNo,
  ).trim()
  if (resolvedEmpNo && resolvedEmpNo !== String(empNo).trim()
    && !String(empNo).includes(resolvedEmpNo)
    && !resolvedEmpNo.includes(String(empNo).trim())) {
    const a = String(empNo).replace(/\D/g, '')
    const b = resolvedEmpNo.replace(/\D/g, '')
    if (!a || !b || !(a.includes(b) || b.includes(a))) {
      return { ok: false, reason: 'emp_mismatch', resolvedEmpNo }
    }
  }

  return {
    ok: true,
    profile: {
      empNo: String(empNo).trim(),
      username: emp.name || emp.empName || emp.userName || empNo,
      department: emp.deptFullName || emp.deptName || emp.deptShortName || emp.orgNamePath || emp.orgName || emp.department || '',
      organization: emp.orgNamePath || emp.orgName || '',
      email: emp.email || emp.mail || '',
      phone: emp.mobile || emp.phone || '',
      raw: emp,
      token,
    },
    result,
  }
}
