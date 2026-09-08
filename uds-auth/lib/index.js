/**
 * uds-auth - UDS Authentication Plugin for DeepSeek Harness
 */

import { requirePermission } from './middleware/auth-middleware.js'
import { computePermissions } from './roles.js'
import { readFile, writeFile } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { createHash, randomBytes } from 'node:crypto'

const __dirname = dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)

// DSH plugin exports
export const name = 'uds-auth'
export const inject = []
export const NS = 'uds-auth'

function tryGet(ctx, name) {
  try { return ctx.get(name) } catch { return undefined }
}

/** Register /uds-auth once; caller must wrap in ctx.effect so reload disposes. */
function registerWebRoute(ctx) {
  const register = (server) => {
    const dispose = server.register({
      kind: 'prefix',
      path: '/uds-auth',
      handler: handleAllRoutes,
    })
    ctx.logger?.info?.('[uds-auth] Route registered: prefix /uds-auth')
    return () => dispose?.()
  }
  const present = tryGet(ctx, 'webServer') ?? ctx.webServer
  if (present !== undefined) return register(present)
  const disposers = []
  let registered = false
  const off = ctx.on('internal/service', (serviceName, value) => {
    if (serviceName !== 'webServer' || registered) return
    registered = true
    disposers.push(register(value))
  })
  return () => {
    off()
    for (const d of disposers) d()
  }
}

const UDS_AUTH_SETTINGS_NAMESPACE = 'uds-auth'
const UDS_AUTH_RPC_CHANNEL = '/uds-auth'

// API prefix for routes
const API_PREFIX = '/uds-auth'

// Config 默认值 — 不依赖 schemastery，纯 JS 对象
// 可配置字段（部署相关），其余内部常量在 INTERNAL 里
const CONFIG_DEFAULTS = {
  uacBaseUrl: 'https://uac.zte.com.cn',
  userSearchUrl: 'https://icenterapi.zte.com.cn/zte-km-icenter-addresearch/user/plain/docs/search',
  loginSystemCode: '100000455558',
  originSystemCode: '',
  workspaceRoot: '',
}

// 内部常量（不暴露给用户，UDS 固定协议）
const INTERNAL = {
  uacQrVerifyPath: '/uacqr/auth/qrcode/verify.serv',
  cookieEmpNo: 'PORTALSSOUser',
  cookieAuthValue: 'PORTALSSOCookie',
  altCookieEmpNo: 'ZTEDPGSSOUser',
  altCookieAuthValue: 'ZTEDPGSSOCookie',
  empNoHeader: 'X-Emp-No',
  authValueHeader: 'X-Auth-Value',
  // Session: 按 empNo 做 key，不需要额外 cookie
  session: {
    storeType: 'memory',        // 单实例足够；多实例/重启用 redis
    redisUrl: 'redis://localhost:6379',
    cookieMaxAge: 1800000,      // 30min
    slidingExpiration: true,
    slidingInterval: 300000,
  },
}

// 懒加载 schemastery Config schema（只在需要注册 DSH 设置面板时用）
// 用 createRequire 因为 schemastery 由 DSH host 运行时提供，不在我们的 package 里
let _ConfigSchema = null
let _DshSettings = null
function loadConfigSchemaAndSettings(ctx) {
  if (_ConfigSchema && _DshSettings) return { schema: _ConfigSchema, settings: _DshSettings }
  try {
    const z = require('@deepseek-ai/schemastery')
    _ConfigSchema = z.object({
      uacBaseUrl: z.string().default(CONFIG_DEFAULTS.uacBaseUrl),
      userSearchUrl: z.string().default(CONFIG_DEFAULTS.userSearchUrl),
      loginSystemCode: z.string().default(CONFIG_DEFAULTS.loginSystemCode),
      originSystemCode: z.string().default(CONFIG_DEFAULTS.originSystemCode),
      workspaceRoot: z.string().default(CONFIG_DEFAULTS.workspaceRoot),
    })
    _DshSettings = require('@deepseek-ai/dsh-settings')
    ctx?.logger?.info?.('[uds-auth] schemastery + dsh-settings loaded')
    return { schema: _ConfigSchema, settings: _DshSettings }
  } catch (err) {
    ctx?.logger?.warn?.('[uds-auth] schemastery/dsh-settings not available: %s', err.message)
    return { schema: null, settings: null }
  }
}

function mergeConfig(custom = {}) {
  return { ...CONFIG_DEFAULTS, ...custom }
}

// Store references
let _sessionStore = null
let _authMiddleware = null
let _apiHandlers = null
let _rolesStore = null
let _currentConfig = null
let _qrcodeLib = null
let _sessionAcl = null
let _userWorkspaces = null
let _pluginCtx = null
let _logger = console

function buildVerifyUrl(uacBaseUrl, uacQrVerifyPath) {
  if (/^https?:\/\//.test(uacQrVerifyPath)) return uacQrVerifyPath
  return (uacBaseUrl.replace(/\/$/, '') + '/' + uacQrVerifyPath.replace(/^\//, ''))
}

// Prefer npm `qrcode`; fall back to vendored copy if present.
async function loadQRCodeLib() {
  if (_qrcodeLib) return _qrcodeLib
  try {
    _qrcodeLib = require('qrcode')
    return _qrcodeLib
  } catch {
    try {
      const libPath = resolve(__dirname, 'qrcode-lib', 'lib', 'browser.js')
      _qrcodeLib = require(libPath)
      return _qrcodeLib
    } catch (e) {
      _logger.error?.('[uds-auth] Failed to load qrcode library:', e)
      return null
    }
  }
}

/** Start a UAC TwoDIMAuth QR challenge (no browser jQuery plugins required). */
function createQrChallenge(config = _currentConfig || {}) {
  const loginSystemCode = String(config.loginSystemCode || CONFIG_DEFAULTS.loginSystemCode)
  const originSystemCode = String(config.originSystemCode || '')
  const qrCodeKey = randomBytes(16).toString('hex')
  const qrCodeValue = randomBytes(16).toString('hex')
  const qrCodeStr = `TwoDIMAuth:${qrCodeKey}:${qrCodeValue}`
  return { qrCodeStr, qrCodeKey, qrCodeValue, loginSystemCode, originSystemCode }
}

async function handleQrStart(req, res) {
  if (req.method !== 'POST' && req.method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Method not allowed' }))
    return
  }
  const challenge = createQrChallenge(_currentConfig)
  res.writeHead(200, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  res.end(JSON.stringify(challenge))
}

// CORS proxy for UAC API
async function handleQRProxy(req, res) {
  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Method not allowed' }))
    return
  }

  let body = ''
  for await (const chunk of req) {
    body += chunk
  }

  try {
    // 不替换 body 中的 loginClientIp（前端已用 127.0.0.1 计算 verifyCode）
    // 但 originSystemCode 如果配置了则替换进 body
    if (_currentConfig.originSystemCode) {
      try {
        const parsed = JSON.parse(body)
        if (!parsed.originSystemCode) parsed.originSystemCode = _currentConfig.originSystemCode
        body = JSON.stringify(parsed)
      } catch { /* body 不是 JSON 就跳过 */ }
    }
    
    const https = await import('node:https')
    const url = new URL(buildVerifyUrl(_currentConfig.uacBaseUrl, INTERNAL.uacQrVerifyPath))
    
    const options = {
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'Origin': _currentConfig.uacBaseUrl,
        'Referer': _currentConfig.uacBaseUrl + '/',
        'X-Requested-With': 'XMLHttpRequest'
      }
    }

    const proxyReq = https.request(options, (proxyRes) => {
      let data = ''
      proxyRes.on('data', chunk => data += chunk)
      proxyRes.on('end', () => {
        res.writeHead(200, { 
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        })
        res.end(data)
      })
    })

    proxyReq.on('error', (err) => {
      res.writeHead(502, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ error: err.message }))
    })

    proxyReq.write(body)
    proxyReq.end()
  } catch (err) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: err.message }))
  }
}

// QR code endpoint
// 静态资源服务：/uds-auth/lib/* → lib/qrcode-lib/*
//              /uds-auth/vendor/* → lib/vendor/*
const MIME = { '.js': 'application/javascript', '.mjs': 'application/javascript', '.json': 'application/json', '.css': 'text/css', '.html': 'text/html' }
function makeStaticHandler(baseDir) {
  return async function handleStatic(req, res) {
    try {
      const url = new URL(req.url, 'http://localhost')
      let rel = url.pathname.replace(/^\/uds-auth\/(lib|vendor)\//, '')
      rel = rel.replace(/\.\.\//g, '').replace(/\.\./g, '')
      const filePath = resolve(baseDir, rel)
      const data = await readFile(filePath)
      const ext = filePath.substring(filePath.lastIndexOf('.'))
      res.writeHead(200, {
        'Content-Type': MIME[ext] || 'application/octet-stream',
        'Cache-Control': 'max-age=3600'
      })
      res.end(data)
    } catch (e) {
      res.writeHead(404, { 'Content-Type': 'text/plain' })
      res.end('Not found')
    }
  }
}
const handleQrcodeStatic = makeStaticHandler(resolve(__dirname, 'qrcode-lib'))
const handleVendorStatic = makeStaticHandler(resolve(__dirname, 'vendor'))

async function handleQRCode(req, res) {
  const url = new URL(req.url, 'http://localhost')
  const data = url.searchParams.get('data')
  
  if (!data) {
    res.writeHead(400, { 'Content-Type': 'text/plain' })
    res.end('Missing data parameter')
    return
  }

  try {
    const qr = await loadQRCodeLib()
    if (!qr || typeof qr.toString !== 'function') {
      throw new Error('qrcode library not available')
    }
    const svg = await new Promise((resolve, reject) => {
      qr.toString(data, { type: 'svg', width: 200, margin: 2 }, (err, str) => {
        if (err) reject(err)
        else resolve(str)
      })
    })
    res.writeHead(200, {
      'Content-Type': 'image/svg+xml',
      'Cache-Control': 'no-cache'
    })
    res.end(svg)
  } catch (err) {
    // 不再生成无纠错码/掩码的无效二维码（会显示成扫不出来的"乱码"）
    console.error('[uds-auth] QR generation error:', err)
    res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('QR generation failed')
  }
}

// 客户端 config.get —— RPC 在 web 端以 HTTP 方式请求 /uds-auth/config.get
async function handleConfigGet(req, res) {
  const c = _currentConfig || {}
  res.writeHead(200, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-cache'
  })
  res.end(JSON.stringify({
    ok: true,
    value: {
      uacBaseUrl: c.uacBaseUrl,
      userSearchUrl: c.userSearchUrl,
      loginSystemCode: c.loginSystemCode,
      originSystemCode: c.originSystemCode,
              workspaceRoot: c.workspaceRoot,
            },
  }))
}

// Calculate verifyCode using Node.js crypto (reliable)
function calculateVerifyCode(qrCodeKey, qrCodeValue, loginClientIp, loginSystemCode, originSystemCode) {
  const source = qrCodeKey + qrCodeValue + loginClientIp + loginSystemCode + originSystemCode
  return createHash('md5').update(source).digest('hex')
}

// VerifyCode calculation endpoint
async function handleVerifyCode(req, res) {
  if (req.method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Method not allowed' }))
    return
  }

  const url = new URL(req.url, 'http://localhost')
  const qrCodeKey = url.searchParams.get('qrCodeKey')
  const qrCodeValue = url.searchParams.get('qrCodeValue')
  const loginClientIp = url.searchParams.get('loginClientIp') || '127.0.0.1'
  const loginSystemCode = url.searchParams.get('loginSystemCode') || '100000455558'
  const originSystemCode = url.searchParams.get('originSystemCode') || ''

  if (!qrCodeKey || !qrCodeValue) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Missing qrCodeKey or qrCodeValue' }))
    return
  }

  const verifyCode = calculateVerifyCode(qrCodeKey, qrCodeValue, loginClientIp, loginSystemCode, originSystemCode)
  
  res.writeHead(200, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*'
  })
  res.end(JSON.stringify({
    qrCodeKey,
    qrCodeValue,
    verifyCode,
    loginClientIp,
    loginSystemCode,
    originSystemCode,
    source: qrCodeKey + qrCodeValue + loginClientIp + loginSystemCode + originSystemCode
  }))
}

// User info proxy — intranet direct (no HTTP_PROXY), empNo+token headers
async function handleUserInfo(req, res) {
  if (req.method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Method not allowed' }))
    return
  }

  const url = new URL(req.url, 'http://localhost')
  const empNo = url.searchParams.get('empNo')
  const token = url.searchParams.get('token')

  if (!empNo || !token) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Missing empNo or token' }))
    return
  }

  try {
    const { searchUserByEmpNoToken } = await import('./uds/user-search.js')
    const out = await searchUserByEmpNoToken({
      userSearchUrl: _currentConfig.userSearchUrl,
      empNo,
      token,
      empNoHeader: INTERNAL.empNoHeader,
      authValueHeader: INTERNAL.authValueHeader,
      origin: _currentConfig.uacBaseUrl,
    })
    if (!out.ok) {
      const status = out.statusCode === 401 || out.statusCode === 403 ? out.statusCode : 502
      res.writeHead(status, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({
        error: 'user search failed',
        reason: out.reason,
        hint: out.hint || 'Ensure userSearchUrl is intranet-reachable and Host does not force HTTP(S)_PROXY for *.zte.com.cn',
        detail: { code: out.code, msg: out.msg, statusCode: out.statusCode },
      }))
      return
    }
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(out.result))
  } catch (err) {
    res.writeHead(502, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: err.message }))
  }
}

function sendJSON(res, code, data) {
  res.statusCode = code >= 200 && code < 300 ? 200 : code
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(data))
}


/** Prefer Secure cookies only on HTTPS — http://127.0.0.1 drops Secure cookies from WS. */
function isHttpsRequest(req) {
  if (req?.socket?.encrypted) return true
  const xf = String(req?.headers?.['x-forwarded-proto'] || '').split(',')[0].trim().toLowerCase()
  return xf === 'https'
}

async function handleFallbackLogin(req, res) {
  let body = ''
  for await (const chunk of req) body += chunk
  let parsed
  try { parsed = JSON.parse(body) } catch { parsed = {} }

  const { username, password } = parsed
  const ip = req.socket?.remoteAddress || 'unknown'

  if (!username || !password) {
    return sendJSON(res, 400, { error: '用户名和密码必填' })
  }
  if (username !== 'administrator') {
    // 不泄露"administrator"是唯一用户名
    return sendJSON(res, 401, { error: '用户名或密码错误' })
  }

  if (!_rolesStore.verifyFallback(password, ip)) {
    return sendJSON(res, 401, { error: '用户名或密码错误' })
  }

  // 登录成功：创建 session，角色 = fallback_admin (等同 super_admin)
  const empNo = 'administrator'
  const userContext = {
    empNo,
    username: 'Fallback Administrator',
    isAuthenticated: true,
    role: 'fallback_admin',
    authenticatedAt: new Date().toISOString(),
    lastActiveAt: new Date().toISOString(),
  }
  await _sessionStore.setex(empNo, Math.floor(INTERNAL.session.cookieMaxAge / 1000), userContext)
  await ensureUserWorkspace(empNo)

  // 给浏览器设 cookie，让后续请求 auth-middleware 能识别
  const fbMaxAge = Math.floor(INTERNAL.session.cookieMaxAge / 1000)
  res.setHeader('Set-Cookie', (() => {
    const secure = isHttpsRequest(req)
    const partsUser = [
      'UDS_FALLBACK_USER=administrator',
      `Max-Age=${fbMaxAge}`,
      'Path=/',
      'HttpOnly',
      'SameSite=Lax',
    ]
    const partsUi = [
      'UDS_FALLBACK_UI=administrator',
      `Max-Age=${fbMaxAge}`,
      'Path=/',
      'SameSite=Lax',
    ]
    if (secure) {
      partsUser.push('Secure')
      partsUi.push('Secure')
    }
    return [partsUser.join('; '), partsUi.join('; ')]
  })())

  sendJSON(res, 200, {
    success: true,
    empNo,
    role: 'fallback_admin',
    message: '兜底管理员登录成功',
  })
}

/** 运行时配置文件路径 — 持久化 _currentConfig 让重启后不丢 */
const RUNTIME_CONFIG_FILE = resolve(__dirname, '..', 'config.runtime.json')

async function saveRuntimeConfig(partial) {
  if (!_currentConfig) throw new Error('配置未初始化')
  // 只允许修改 4 个可配置字段
  const allowed = ['uacBaseUrl', 'userSearchUrl', 'loginSystemCode', 'originSystemCode', 'workspaceRoot']
  for (const k of allowed) {
    if (partial[k] !== undefined) {
      _currentConfig[k] = String(partial[k])
    }
  }
  // 写运行时配置文件（不覆盖原始 config.default.yaml）
  try {
    await writeFile(RUNTIME_CONFIG_FILE, JSON.stringify(_currentConfig, null, 2), 'utf-8')
  } catch (err) {
    // 文件写失败不影响内存配置（服务端仍然生效）
    console.warn('[uds-auth] Failed to write runtime config:', err.message)
  }
}

// 统一入口：单个 prefix 路由 handler，内部自行分发
async function handleAllRoutes(req, res) {
  try {
    const url = new URL(req.url, 'http://localhost')
    const pathname = url.pathname.replace(/\/+$/, '') || '/'
    const method = (req.method || 'GET').toUpperCase()

    // 静态资源：/uds-auth/vendor/*
    if (pathname.startsWith('/uds-auth/vendor/')) {
      return await handleVendorStatic(req, res)
    }
    // 静态资源：/uds-auth/lib/*
    if (pathname.startsWith('/uds-auth/lib/')) {
      return await handleQrcodeStatic(req, res)
    }

    // QR 生成
    if (pathname === '/uds-auth/qr' && method === 'GET') {
      return await handleQRCode(req, res)
    }

    // QR 挑战（扫码登录入口）
    if (pathname === '/uds-auth/qr-start' && (method === 'GET' || method === 'POST')) {
      return await handleQrStart(req, res)
    }

    // QR 代理
    if (pathname === '/uds-auth/qr-proxy' && method === 'POST') {
      return await handleQRProxy(req, res)
    }

    // verifyCode 计算
    if (pathname === '/uds-auth/verify-code' && method === 'GET') {
      return await handleVerifyCode(req, res)
    }

    // 用户信息代理
    if (pathname === '/uds-auth/user-info' && method === 'GET') {
      return await handleUserInfo(req, res)
    }

    // 客户端配置（RPC config.get 在 web 端走 HTTP）
    if (pathname === '/uds-auth/config.get' && (method === 'GET' || method === 'POST')) {
      return await handleConfigGet(req, res)
    }

    // 下面都是 /uds-auth/api/* — 走 handleRequest（含鉴权）
    if (pathname.startsWith('/uds-auth/api/')) {
      return await handleRequest(req, res)
    }

    // 未知路径
    res.statusCode = 404
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ error: 'Not found', path: pathname }))
  } catch (err) {
    console.error('[uds-auth] handleAllRoutes error:', err)
    res.statusCode = 500
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ error: err.message || 'Internal error' }))
  }
}

function handleRequest(req, res) {
  const ctx2 = { req, res }
  _authMiddleware(ctx2, async () => {
    if (ctx2.empNo && ctx2.empNo !== 'administrator') {
      try { await ensureUserWorkspace(ctx2.empNo) } catch { /* ignore */ }
    }
    // bootstrap 已在 auth-middleware.resolveRole 中完成（勿用 !ctx2.role，getRole 恒有值）

    const url = new URL(req.url, 'http://localhost').pathname.replace(API_PREFIX, '') || '/'
    const method = req.method

    // 公开端点（不需要登录态也能访问）
    if (url === '/api/fallback/login' && method === 'POST') {
      await handleFallbackLogin(req, res)
      return
    }
    if (url === '/api/fallback/status' && method === 'GET') {
      return sendJSON(res, 200, { enabled: _rolesStore.isFallbackEnabled() })
    }

    // 以下都需要登录态
    if (!ctx2.empNo) {
      return sendJSON(res, 401, { error: '未登录' })
    }

    // 用户管理 (super_admin only)
    if (url === '/api/users' && method === 'GET') {
      await _apiHandlers.listUsers(ctx2); return
    }
    if (url === '/api/users/role' && method === 'POST') {
      await _apiHandlers.setUserRole(ctx2); return
    }
    if (url === '/api/users' && method === 'POST') {
      await _apiHandlers.addUser(ctx2); return
    }
    if (url === '/api/users/delete' && method === 'POST') {
      await _apiHandlers.removeUser(ctx2); return
    }

    // Fallback admin 管理 (super_admin only)
    if (url === '/api/fallback/password' && method === 'POST') {
      await _apiHandlers.setFallbackPassword(ctx2); return
    }
    if (url === '/api/fallback/clear' && method === 'POST') {
      await _apiHandlers.clearFallbackPassword(ctx2); return
    }

    // 配置端点 (admin / super_admin：canAccessSettings)
    if (url === '/api/config' && method === 'GET') {
      if (!requirePermission(ctx2, 'canAccessSettings')) {
        return sendJSON(res, 403, { error: '当前账号无设置权限' })
      }
      sendJSON(res, 200, { config: _currentConfig })
      return
    }
    if (url === '/api/config' && method === 'POST') {
      if (!requirePermission(ctx2, 'canAccessSettings')) {
        return sendJSON(res, 403, { error: '当前账号无设置权限' })
      }
      let body = ''
      for await (const chunk of req) body += chunk
      let parsed
      try { parsed = JSON.parse(body) } catch { parsed = {} }
      try {
        await saveRuntimeConfig(parsed)
        sendJSON(res, 200, { message: '配置已保存' })
      } catch(err) {
        sendJSON(res, 400, { error: err.message })
      }
      return
    }

    // 基础端点
    if (url === '/api/me' && method === 'GET') {
      if (ctx2.empNo) {
        try { ctx2.provisionedWorkspace = await ensureUserWorkspace(ctx2.empNo) } catch { ctx2.provisionedWorkspace = null }
      }
      await _apiHandlers.getCurrentUser(ctx2); return
    }
    if (url === '/api/logout' && method === 'POST') {
      await _apiHandlers.logout(ctx2); return
    }

    sendJSON(res, 200, {
      success: true,
      user: ctx2.userContext,
      empNo: ctx2.empNo,
      role: ctx2.role,
      permissions: ctx2.permissions,
    })
  }).catch(err => {
    sendJSON(res, 500, { error: err.message })
  })
}

function installSettingsSection(ctx, entry, hooks) {
  const { schema: ConfigSchema, settings: DshSettings } = loadConfigSchemaAndSettings(ctx)
  if (!ConfigSchema || !DshSettings) {
    ctx.logger?.warn?.('[uds-auth] cannot register settings panel — schemastery/dsh-settings unavailable')
    return
  }

  const hooksArg = {
    setSource: (current) => {
      hooks.setSource?.(current)
      _currentConfig = current
    },
    onChange: () => {
      hooks.onChange?.()
    }
  }

  // 和 netxops 完全对齐的注册方式
  const legacy = DshSettings.installSettingsSection
  if (typeof legacy === 'function') {
    ctx.logger?.info?.('[uds-auth] registering settings panel (legacy API)')
    legacy(ctx, UDS_AUTH_SETTINGS_NAMESPACE, ConfigSchema, entry, hooksArg)
    return
  }
  ctx.inject(['settings'], (settingsCtx) => {
    ctx.logger?.info?.('[uds-auth] registering settings panel (new API)')
    settingsCtx.settings.installSection(ctx, UDS_AUTH_SETTINGS_NAMESPACE, ConfigSchema, entry, hooksArg)
  })
}


let _workspaceRegistry = null

async function ensureUserWorkspace(empNo) {
  if (!_userWorkspaces) return null
  try {
    return await _userWorkspaces.ensureUserWorkspace(
      { workspaceRegistryHandle: _workspaceRegistry },
      _currentConfig?.workspaceRoot,
      empNo,
    )
  } catch (err) {
    console.warn('[uds-auth] ensureUserWorkspace failed:', err.message)
    return null
  }
}

export async function apply(ctx, config = {}) {
  let source = () => mergeConfig(config)
  _currentConfig = source()
  _logger = ctx.logger || console

  ctx.logger?.info?.('[uds-auth] Loading...')

  installSettingsSection(ctx, source(), {
    setSource: (current) => {
      source = typeof current === 'function' ? current : () => current
      _currentConfig = source()
    },
    onChange: () => {
      _currentConfig = source()
      ctx.logger?.info?.('[uds-auth] settings updated')
    }
  })

  // Do NOT rpc.handle('/uds-auth') — same path as webServer prefix → duplicate route / 415.
  // Client uses HTTP /uds-auth/config.get instead.
  await initServices(ctx, source())

  // Register prefix once; wrap in effect so reload disposes cleanly.
  ctx.inject(['webServer'], (wctx) => {
    wctx.effect(() => registerWebRoute(wctx), 'uds-auth: web route')
  })

  ctx.logger?.info?.('[uds-auth] Host ready')
}

async function initServices(ctx, config) {
  try {
    const { createSessionStore } = await import('./session/factory.js')
    const { createAuthMiddleware } = await import('./middleware/auth-middleware.js')
    const { createApiHandlers } = await import('./api.js')
    const { RolesStore } = await import('./roles.js')
    const { SessionAclStore } = await import('./session-acl.js')
    const { UserWorkspaceStore } = await import('./workspace-provision.js')
    const { patchWebServerWithIdentity, resolveIdentityFromRequest, resolveIdentityFromRequestSync, installDshAcl } = await import('./dsh-acl.js')

    _pluginCtx = ctx
    _currentConfig = config

    try {
      const raw = await readFile(RUNTIME_CONFIG_FILE, 'utf-8')
      const rt = JSON.parse(raw)
      if (rt && typeof rt === 'object') {
        for (const k of Object.keys(rt)) {
          _currentConfig[k] = rt[k]
        }
      }
    } catch { /* runtime config optional */ }

    _sessionStore = await createSessionStore(INTERNAL.session)

    const rolesFile = resolve(__dirname, '..', 'roles.json')
    _rolesStore = new RolesStore({ rolesFile })
    await _rolesStore.init()

    _sessionAcl = new SessionAclStore({ ownersFile: resolve(__dirname, '..', 'session-owners.json') })
    await _sessionAcl.init()

    _userWorkspaces = new UserWorkspaceStore({ mapFile: resolve(__dirname, '..', 'user-workspaces.json') })
    await _userWorkspaces.init()

    _authMiddleware = createAuthMiddleware({
      userSearchUrl: _currentConfig.userSearchUrl,
      udsAuth: {
        baseUrl: _currentConfig.uacBaseUrl,
        systemCode: _currentConfig.loginSystemCode,
        userSearchUrl: _currentConfig.userSearchUrl,
        empNoHeader: INTERNAL.empNoHeader,
        authValueHeader: INTERNAL.authValueHeader,
      },
      session: INTERNAL.session,
    }, _sessionStore, _rolesStore)
    _apiHandlers = createApiHandlers({ session: INTERNAL.session }, _sessionStore, _rolesStore)

    const identityDeps = {
      sessionStore: _sessionStore,
      rolesStore: _rolesStore,
    }
    const resolveIdentity = (req) => resolveIdentityFromRequest(req, identityDeps)
    const resolveIdentitySync = (req) => resolveIdentityFromRequestSync(req, identityDeps)

    const patchServer = (server) => {
      patchWebServerWithIdentity(server, resolveIdentity, resolveIdentitySync)
    }
    const present = tryGet(ctx, 'webServer')
    if (present) patchServer(present)
    ctx.inject(['webServer'], (wctx) => {
      patchServer(wctx.webServer)
    })

    ctx.inject(['workspaceRegistry'], (wctx) => {
      _workspaceRegistry = wctx.workspaceRegistry
      ctx.logger?.info?.('[uds-auth] workspaceRegistry ready')
    })

    installDshAcl(ctx, {
      sessionAcl: _sessionAcl,
      userWorkspaces: _userWorkspaces,
      getWorkspaceRoot: () => _currentConfig?.workspaceRoot,
      rolesStore: _rolesStore,
      ensureUserWorkspace,
      getWorkspaceRegistry: () => _workspaceRegistry,
    })

    ctx.logger?.info?.('[uds-auth] Initialized (ACL + workspaces)')
  } catch (err) {
    ctx.logger?.error?.('[uds-auth] Init failed: ' + (err.message || err))
  }
}
