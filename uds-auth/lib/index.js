/**
 * uds-auth - UDS Authentication Plugin for DeepSeek Harness
 */

import { requirePermission } from './middleware/auth-middleware.js'
import { computePermissions } from './roles.js'
import { readFile, writeFile } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

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
  const present = tryGet(ctx, 'webServer')
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
  const qrCodeKey = crypto.randomBytes(16).toString('hex')
  const qrCodeValue = crypto.randomBytes(16).toString('hex')
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

// User info proxy - bypasses CORS by server-side fetching icenterapi
async function handleUserInfo(req, res) {
  if (req.method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Method not allowed' }))
    return
  }

  const url = new URL(req.url, 'http://localhost')
  const empNo = url.searchParams.get('empNo')
  const token = url.searchParams.get('token')

  if (!empNo) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: 'Missing empNo' }))
    return
  }

  try {
    const https = await import('node:https')
    const targetUrl = new URL(_currentConfig.userSearchUrl)
    const body = JSON.stringify({ employeeShortId: empNo, enableLabel: true, keyword: empNo })

    const headers = {
      'Content-Type': 'application/json;charset=UTF-8',
      'Content-Length': Buffer.byteLength(body),
      [INTERNAL.empNoHeader]: empNo,
      'Origin': _currentConfig.uacBaseUrl,
      'Referer': _currentConfig.uacBaseUrl + '/'
    }
    if (token) headers[INTERNAL.authValueHeader] = token

    const result = await new Promise((resolve, reject) => {
      const proxyReq = https.request({
        hostname: targetUrl.hostname,
        path: targetUrl.pathname,
        method: 'POST',
        headers
      }, (proxyRes) => {
        let data = ''
        proxyRes.on('data', chunk => data += chunk)
        proxyRes.on('end', () => {
          try { resolve(JSON.parse(data)) } catch (e) { resolve({ raw: data }) }
        })
      })
      proxyReq.on('error', reject)
      proxyReq.write(body)
      proxyReq.end()
    })

    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(result))
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

  // 给浏览器设 cookie，让后续请求 auth-middleware 能识别
  res.setHeader('Set-Cookie', [
    'UDS_FALLBACK_USER=administrator',
    `Max-Age=${Math.floor(INTERNAL.session.cookieMaxAge / 1000)}`,
    'Path=/',
    'Secure',
    'HttpOnly',
    'SameSite=Lax',
  ].join('; '))

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
  const allowed = ['uacBaseUrl', 'userSearchUrl', 'loginSystemCode', 'originSystemCode']
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
    // 首次部署 bootstrap: 第一个有 UDS 凭证的用户 = super_admin
    if (ctx2.empNo && !ctx2.role) {
      const { role, bootstrapped } = await _rolesStore.bootstrapFirstUser(ctx2.empNo)
      ctx2.role = role
      ctx2.permissions = computePermissions(role)
      if (bootstrapped) {
        ctx.logger?.info?.(`[uds-auth] BOOTSTRAP: ${ctx2.empNo} is now super_admin`)
      }
    }

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

    // 配置端点 (super_admin only)
    if (url === '/api/config' && method === 'GET') {
      if (!requirePermission(ctx2, 'super_admin')) {
        return sendJSON(res, 403, { error: '只有超级管理员可以查看配置' })
      }
      sendJSON(res, 200, { config: _currentConfig })
      return
    }
    if (url === '/api/config' && method === 'POST') {
      if (!requirePermission(ctx2, 'super_admin')) {
        return sendJSON(res, 403, { error: '只有超级管理员可以修改配置' })
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

export async function apply(ctx, config = {}) {
  let source = () => mergeConfig(config)
  _currentConfig = source()

  ctx.logger?.info?.('[uds-auth] Loading...')

  // Settings 注册 + RPC 注册：不依赖 webServer
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

  ctx.inject(['connection'], (connCtx) => {
    const rpc = connCtx.connection?.rpc
    if (!rpc || typeof rpc.handle !== 'function') {
      ctx.logger?.warn?.('[uds-auth] connection.rpc.handle unavailable — client config UI disabled')
      return
    }
    connCtx.effect(() => {
      const dispose = rpc.handle(UDS_AUTH_RPC_CHANNEL, async (endpoint) => {
        if (endpoint === 'config.get') {
          const c = source()
          return {
            ok: true,
            value: {
              uacBaseUrl: c.uacBaseUrl,
              userSearchUrl: c.userSearchUrl,
              loginSystemCode: c.loginSystemCode,
              originSystemCode: c.originSystemCode,
            }
          }
        }
        return { ok: false, error: 'unknown_endpoint' }
      })
      return () => dispose?.()
    }, 'uds-auth: rpc')
  })
  
  // 初始化内部服务（session store, roles, auth middleware 等）
  await initServices(ctx, source())

  // 注册 webServer 路由（可能 webServer 已就绪，也可能需要等待）
  registerWebRoute(ctx)
  
  ctx.logger?.info?.('[uds-auth] Host ready')
}

async function initServices(ctx, config) {
  try {
    const { createSessionStore } = await import('./session/factory.js')
    const { createAuthMiddleware } = await import('./middleware/auth-middleware.js')
    const { createApiHandlers } = await import('./api.js')
    const { RolesStore } = await import('./roles.js')
    
    _currentConfig = config

    // 加载运行时配置覆盖（如果存在）
    try {
      const raw = await readFile(RUNTIME_CONFIG_FILE, 'utf-8')
      const rt = JSON.parse(raw)
      if (rt && typeof rt === 'object') {
        for (const k of Object.keys(rt)) {
          _currentConfig[k] = rt[k]
        }
      }
    } catch { /* runtime config 不存在是正常的 */ }
    
    _sessionStore = await createSessionStore(INTERNAL.session)

    // RolesStore — 持久化到 roles.json
    const rolesFile = resolve(__dirname, '..', 'roles.json')
    _rolesStore = new RolesStore({ rolesFile })
    await _rolesStore.init()
    
    _authMiddleware = createAuthMiddleware({
      udsAuth: {
        baseUrl: config.uacBaseUrl,
        systemCode: config.loginSystemCode,
        empNoHeader: INTERNAL.empNoHeader,
        authValueHeader: INTERNAL.authValueHeader,
      },
      session: INTERNAL.session,
    }, _sessionStore, _rolesStore)
    _apiHandlers = createApiHandlers({ session: INTERNAL.session }, _sessionStore, _rolesStore)
    
    ctx.logger?.info?.('[uds-auth] Initialized')
  } catch (err) {
    ctx.logger?.error?.('[uds-auth] Init failed: ' + (err.message || err))
  }
}
