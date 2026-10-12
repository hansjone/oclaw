/**
 * uds-auth - UDS Authentication Plugin for DeepSeek Harness
 */

import { requirePermission } from './middleware/auth-middleware.js'
import { computePermissions } from './roles.js'
import { apiError, apiOk, resolveLocale } from './i18n.js'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { resolve, dirname, isAbsolute, join } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { createHash, randomBytes } from 'node:crypto'
import {
  logLocalAdminStatus,
  appendLocalAdminCookie,
  isLocalAdminBoxConfigured,
  readLocalAdminBox,
  openLocalAdminBoxAsync,
  allowUnlockAttempt,
  buildLocalAdminUserContext,
  LOCAL_ADMIN_BOX_ENV,
} from './local-admin.js'
import { SessionBridgeStore } from './session-bridge.js'
import { runAsHost } from './context.js'
import {
  buildSessionCookie,
  clearSessionCookie,
  extractSessionBearerAsync,
  SESSION_COOKIE,
} from './session/request-auth.js'
import { checkRequestOrigin, requireJsonContentType } from './utils/origin-guard.js'
import { requestIsLoopback } from './skill-credentials.js'
import { atomicWriteJson } from './utils/atomic-write.js'
import { readBodyLimited, MAX_QR_PROXY_BODY, MAX_QR_DATA_LEN, DEFAULT_MAX_BODY } from './utils/read-body.js'
import { RateLimiter, clientKey } from './utils/rate-limit.js'
import { audit } from './utils/audit-log.js'
import { QrChallengeStore, qrLoginCredentials } from './qr-challenge.js'
import { migrateState } from './state-migration.js'
import { protectProfileDirectory } from './profile-security.js'
import { gatewayPolicy, assertGatewayContract } from './gateway-policy.js'

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
  /** Explicit first admin when roles.json is empty (also: UDS_AUTH_INITIAL_ADMIN) */
  initialAdminEmpNo: '',
  /** When roles already exist, auto-register unknown UAC users as role=user */
  allowOpenRegistration: true,
  /** UI 退出时是否保留 skill 凭证缓存（默认保留，供 cron/skill） */
  retainSkillCredentialsOnLogout: true,
  /** skill 凭证 TTL（秒），默认 7 天 */
  skillCredentialTtlSeconds: 7 * 24 * 60 * 60,
  /** outbound 白名单 host（逗号分隔或数组） */
  outboundAllowedHosts: 'icenterapi.zte.com.cn,icentermsg.dt.zte.com.cn',
  /** SEC-05: raw /agent-credentials token response off by default */
  allowRawAgentToken: false,
  /** R13: optional exact Host allowlist (comma/array). Empty = compare Origin↔Host only. */
  trustedHosts: '',
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
  // Session: opaque bearer in UDS_SESSION cookie / Desktop bridge
  session: {
    storeType: 'memory',        // 单实例足够；多实例需共享 store，不可静默切 memory
    redisUrl: 'redis://localhost:6379',
    cookieMaxAge: 1800000,      // 30min idle TTL
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
      retainSkillCredentialsOnLogout: z.boolean().default(CONFIG_DEFAULTS.retainSkillCredentialsOnLogout),
      skillCredentialTtlSeconds: z.number().default(CONFIG_DEFAULTS.skillCredentialTtlSeconds),
      outboundAllowedHosts: z.string().default(CONFIG_DEFAULTS.outboundAllowedHosts),
      initialAdminEmpNo: z.string().default(CONFIG_DEFAULTS.initialAdminEmpNo),
      allowOpenRegistration: z.boolean().default(CONFIG_DEFAULTS.allowOpenRegistration),
      allowRawAgentToken: z.boolean().default(CONFIG_DEFAULTS.allowRawAgentToken),
      trustedHosts: z.string().default(CONFIG_DEFAULTS.trustedHosts),
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

/**
 * A11: durable state lives under a profile data dir, not only the install tree.
 * Override with UDS_AUTH_DATA_DIR (absolute) or config.dataDir.
 */
function resolvePluginDataDir(config = _currentConfig) {
  const fromEnv = String(process.env.UDS_AUTH_DATA_DIR || '').trim()
  if (fromEnv) return isAbsolute(fromEnv) ? fromEnv : resolve(process.cwd(), fromEnv)
  const fromCfg = String(config?.dataDir || '').trim()
  if (fromCfg) return isAbsolute(fromCfg) ? fromCfg : resolve(process.cwd(), fromCfg)
  return join(homedir(), '.uds-auth')
}

/** DSH/schemastery config objects may be frozen — always clone before mutate. */
function asMutableConfig(config) {
  return { ...(config && typeof config === 'object' ? config : {}) }
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
let _skillCredentials = null
let _agentAuthHandlers = null
/** @type {import('./task-capability.js').TaskCapabilityStore | null} */
let _taskCapabilities = null
/** @type {SessionBridgeStore | null} */
let _sessionBridge = null
/** SEC-20: false until init completes; routes return 503 when unready. */
let _pluginReady = false
let _pluginReadyError = null
const _loginLimiter = new RateLimiter({ windowMs: 60_000, max: 20 })
const _qrLimiter = new RateLimiter({ windowMs: 60_000, max: 60 })
/** R13: server-side QR challenge TTL + one-time consume */
const QR_CHALLENGE_TTL_MS = 5 * 60 * 1000
const _qrChallenges = new QrChallengeStore({ ttlMs: QR_CHALLENGE_TTL_MS })
const MAX_QR_UPSTREAM_BYTES = 256 * 1024

/**
 * Mint Desktop bridge using the same bearer as the local auth session.
 * @param {string} empNo
 * @param {string} [kind]
 * @param {string} [ssoToken]
 * @param {string} [bearer] local session bearer — must match session store
 */
function mintBridge(empNo, kind = 'fallback', ssoToken, bearer) {
  if (!_sessionBridge) return null
  try {
    const minted = _sessionBridge.mint({
      empNo,
      kind,
      ssoToken,
      token: bearer || undefined,
    })
    return {
      empNo: minted.empNo,
      kind: minted.kind,
      token: minted.token,
      exp: minted.exp,
    }
  } catch (err) {
    _logger?.warn?.('[uds-auth] mintBridge failed: %s', err.message)
    return null
  }
}

/** Create local session + bridge sharing the same bearer. */
async function mintLoginSession(empNo, userContext, kind = 'uds', ssoToken) {
  const live = () => !_rolesStore?.isDisabled(empNo)
    && (kind !== 'fallback' || (_rolesStore.isFallbackEnabled()
      && userContext.fallbackCredVersion === _rolesStore.getFallbackCredVersion()))
  if (!live()) throw Object.assign(new Error('invalid_credentials'), { code: 'invalid_credentials' })
  const ttl = Math.floor(INTERNAL.session.cookieMaxAge / 1000)
  const { sessionId, bearer } = await _sessionStore.create(
    { ...userContext, empNo },
    ttl,
  )
  if (!live()) {
    await _sessionStore.revokeSession(sessionId)
    throw Object.assign(new Error('invalid_credentials'), { code: 'invalid_credentials' })
  }
  const bridge = mintBridge(empNo, kind, ssoToken, bearer)
  return { sessionId, bearer, bridge }
}

function appendSessionCookie(req, res, bearer, extraCookies = []) {
  const ttl = Math.floor(INTERNAL.session.cookieMaxAge / 1000)
  const secure = isHttpsRequest(req)
  const sessionCookie = buildSessionCookie(bearer, ttl, { secure })
  const list = [sessionCookie, ...extraCookies]
  const prev = res.getHeader?.('Set-Cookie')
  if (prev) {
    const p = Array.isArray(prev) ? prev : [prev]
    res.setHeader('Set-Cookie', [...p, ...list])
  } else {
    res.setHeader('Set-Cookie', list)
  }
}

function buildVerifyUrl(uacBaseUrl, uacQrVerifyPath) {
  if (/^https?:\/\//.test(uacQrVerifyPath)) return uacQrVerifyPath
  return (uacBaseUrl.replace(/\/$/, '') + '/' + uacQrVerifyPath.replace(/^\//, ''))
}

// Prefer offline bundle (shipped in tgz); fall back to npm / legacy vendored tree.
async function loadQRCodeLib() {
  if (_qrcodeLib) return _qrcodeLib
  const candidates = [
    resolve(__dirname, 'qrcode-bundled.cjs'),
    'qrcode',
    resolve(__dirname, 'qrcode-lib', 'lib', 'browser.js'),
  ]
  for (const candidate of candidates) {
    try {
      _qrcodeLib = require(candidate)
      return _qrcodeLib
    } catch {
      // try next
    }
  }
  _logger.error?.('[uds-auth] Failed to load qrcode library (no bundled/npm/vendored copy)')
  return null
}

/** Start a UAC TwoDIMAuth QR challenge (no browser jQuery plugins required). */
function createQrChallenge(config = _currentConfig || {}) {
  return _qrChallenges.create({ loginSystemCode: String(config.loginSystemCode || CONFIG_DEFAULTS.loginSystemCode),
    originSystemCode: String(config.originSystemCode || '') })
}

function peekQrChallenge(key, value, binding) { return _qrChallenges.peek(key, value, binding) }
function consumeQrChallenge(key, value, binding) { return _qrChallenges.consume(key, value, binding) }
function isQrLoginSuccessPayload(payload) { return !!qrLoginCredentials(payload) }

async function handleQrStart(req, res) {
  if (req.method !== 'POST' && req.method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('method_not_allowed', localeOf(req))))
    return
  }
  if (!_qrLimiter.allow(clientKey(req))) {
    res.writeHead(429, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('rate_limited', localeOf(req))))
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
    res.end(JSON.stringify(apiError('method_not_allowed', localeOf(req))))
    return
  }
  if (!_qrLimiter.allow(clientKey(req))) {
    res.writeHead(429, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('rate_limited', localeOf(req))))
    return
  }

  let body
  try {
    body = await readBodyLimited(req, { maxBytes: MAX_QR_PROXY_BODY })
  } catch (err) {
    const status = err.statusCode || 413
    res.writeHead(status, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError(err.code || 'payload_too_large', localeOf(req))))
    return
  }

  try {
    let parsedBody = {}
    try { parsedBody = JSON.parse(body) } catch { parsedBody = {} }
    // A04: peek only — do not consume until upstream confirms login.
    const peeked = peekQrChallenge(parsedBody.qrCodeKey, parsedBody.qrCodeValue, req.headers['x-uds-qr-binding'])
    if (!peeked.ok) {
      res.writeHead(400, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify(apiError(peeked.reason || 'qr_unknown', localeOf(req))))
      return
    }
    // Only send contract fields. Browser binding and arbitrary body fields stay local.
    parsedBody = {
      qrCodeKey: parsedBody.qrCodeKey, qrCodeValue: parsedBody.qrCodeValue,
      loginClientIp: '127.0.0.1', loginSystemCode: peeked.row.loginSystemCode,
      originSystemCode: peeked.row.originSystemCode,
      verifyCode: calculateVerifyCode(parsedBody.qrCodeKey, parsedBody.qrCodeValue, '127.0.0.1',
        peeked.row.loginSystemCode, peeked.row.originSystemCode),
    }
    body = JSON.stringify(parsedBody)
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
      },
      timeout: 15_000,
    }

    const proxyReq = https.request(options, (proxyRes) => {
      const chunks = []
      let total = 0
      let aborted = false
      proxyRes.on('data', (chunk) => {
        if (aborted) return
        total += chunk.length
        if (total > MAX_QR_UPSTREAM_BYTES) {
          aborted = true
          try { proxyRes.destroy() } catch { /* ignore */ }
          if (!res.headersSent) {
            res.writeHead(502, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify(apiError('upstream_too_large', localeOf(req))))
          }
          return
        }
        chunks.push(chunk)
      })
      proxyRes.on('end', () => {
        if (aborted || res.headersSent) return
        void (async () => {
          let payload
          try { payload = JSON.parse(Buffer.concat(chunks).toString('utf8')) } catch {
            return sendErr(res, req, 502, 'invalid_upstream_response')
          }
          if (proxyRes.statusCode < 200 || proxyRes.statusCode >= 300) {
            return sendErr(res, req, 502, 'upstream_error')
          }
          const credentials = qrLoginCredentials(payload)
          if (!credentials) {
            // Pending polls preserve the challenge. Do not return upstream secrets/errors verbatim.
            const top = String(payload?.code?.code ?? payload?.code ?? '')
            const boCode = String(payload?.bo?.code ?? '')
            if (top === '0000' && ['4002', '1002'].includes(boCode)) {
              return sendJSON(res, 200, { code: { code: top }, bo: { code: boCode } })
            }
            return sendErr(res, req, 502, 'invalid_upstream_response')
          }
          const consumed = consumeQrChallenge(parsedBody.qrCodeKey, parsedBody.qrCodeValue,
            req.headers['x-uds-qr-binding'])
          if (!consumed.ok) return sendErr(res, req, 409, consumed.reason)
          // Reserve once before asynchronous profile validation or session minting.
          const profile = await _authMiddleware.verifyEmpNoAndToken(credentials.empNo, credentials.token)
          if (!profile) return sendErr(res, req, 401, 'invalid_credentials')
          const id = profile.empNo || credentials.empNo
          const role = await _authMiddleware.resolveRoleOnLogin(id)
          const now = new Date().toISOString()
          const userContext = { empNo: id, userId: id, username: profile.username || id,
            displayName: profile.username || id, department: profile.department || '',
            organization: profile.organization || profile.department || '',
            email: profile.email || '', phone: profile.phone || '', token: credentials.token,
            isAuthenticated: true, authMode: 'token+profile', authenticatedAt: now,
            lastActiveAt: now, sessionCreatedAt: now }
          await ensureUserWorkspace(id)
          const { bearer, bridge } = await mintLoginSession(id, userContext, 'uds', credentials.token)
          appendSessionCookie(req, res, bearer)
          sendJSON(res, 200, { code: { code: '0000' }, bo: { code: '0000' },
            auth: { success: true, empNo: id, role, bridge,
              userContext: { empNo: id, username: userContext.username, role, isAuthenticated: true } } })
        })().catch(err => {
          if (!res.headersSent) sendErr(res, req, 502, err.code || 'upstream_error')
        })
      })
      proxyRes.on('error', () => {
        if (!res.headersSent) sendErr(res, req, 502, 'upstream_error')
      })
    })

    proxyReq.on('timeout', () => {
      try { proxyReq.destroy() } catch { /* ignore */ }
    })

    proxyReq.on('error', (err) => {
      if (!res.headersSent) sendErr(res, req, 502, 'upstream_error')
    })

    proxyReq.write(body)
    proxyReq.end()
  } catch (err) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: err.message }))
  }
}

// SEC-01: generic /uds-auth/lib/* and /vendor/* file serving removed (path traversal).
// QR library is bundled as qrcode-bundled.cjs and loaded in-process only.

async function handleQRCode(req, res) {
  if (!_qrLimiter.allow(clientKey(req))) {
    res.writeHead(429, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('rate_limited', localeOf(req))))
    return
  }
  const url = new URL(req.url, 'http://localhost')
  const data = url.searchParams.get('data')
  
  if (!data) {
    res.writeHead(400, { 'Content-Type': 'text/plain' })
    res.end('Missing data parameter')
    return
  }
  if (String(data).length > MAX_QR_DATA_LEN) {
    res.writeHead(413, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('payload_too_large', localeOf(req))))
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
      retainSkillCredentialsOnLogout: c.retainSkillCredentialsOnLogout !== false,
      skillCredentialTtlSeconds: c.skillCredentialTtlSeconds,
      outboundAllowedHosts: c.outboundAllowedHosts,
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
    res.end(JSON.stringify(apiError('method_not_allowed', localeOf(req))))
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
    res.end(JSON.stringify(apiError('missing_qr_params', localeOf(req))))
    return
  }

  const challenge = peekQrChallenge(qrCodeKey, qrCodeValue, req.headers['x-uds-qr-binding'])
  if (!challenge.ok) return sendErr(res, req, 400, challenge.reason)
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

// User info proxy — intranet direct (no HTTP_PROXY). T03: token never via URL query.
async function handleUserInfo(req, res) {
  const method = (req.method || 'GET').toUpperCase()
  if (method !== 'POST' && method !== 'GET') {
    res.writeHead(405, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('method_not_allowed', localeOf(req))))
    return
  }

  const url = new URL(req.url, 'http://localhost')
  // Reject token in query on any method (access logs / Referer leak).
  if (url.searchParams.get('token') || url.searchParams.get('authValue')) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('token_in_query_forbidden', localeOf(req))))
    return
  }

  let empNo = null
  let token = null
  const headers = req.headers || {}
  if (method === 'POST') {
    let body = {}
    try {
      const raw = await readBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
      try { body = JSON.parse(raw || '{}') } catch { body = {} }
    } catch (err) {
      res.writeHead(err.statusCode || 413, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify(apiError(err.code || 'payload_too_large', localeOf(req))))
      return
    }
    empNo = body.empNo || headers[INTERNAL.empNoHeader.toLowerCase()] || headers['x-emp-no']
    token = body.token || body.authValue
      || headers[INTERNAL.authValueHeader.toLowerCase()]
      || headers['x-auth-value']
  } else {
    // GET: headers only (no query credentials).
    empNo = headers[INTERNAL.empNoHeader.toLowerCase()] || headers['x-emp-no']
    token = headers[INTERNAL.authValueHeader.toLowerCase()] || headers['x-auth-value']
  }
  empNo = empNo != null ? String(empNo).trim() : ''
  token = token != null ? String(token).trim() : ''

  if (!empNo || !token) {
    res.writeHead(400, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(apiError('missing_emp_token', localeOf(req))))
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
        ...apiError('user_search_failed', localeOf(req)),
        reason: out.reason,
        hint: out.hint || 'Ensure userSearchUrl is intranet-reachable and Host does not force HTTP(S)_PROXY for *.zte.com.cn',
        detail: { code: out.code, msg: out.msg, statusCode: out.statusCode },
      }))
      return
    }
    // R07: client expects code + non-empty bo list (not only upstream code).
    // Return whitelist profile only — never raw UAC blob / full token.
    const profile = out.profile || {}
    const safeRow = {
      employeeShortId: profile.empNo,
      empNo: profile.empNo,
      name: profile.username || profile.empNo,
      deptFullName: profile.department || '',
      orgNamePath: profile.organization || '',
      email: profile.email || '',
    }
    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({
      code: { code: '0000' },
      bo: [safeRow],
      profile: {
        empNo: profile.empNo,
        username: profile.username || null,
        displayName: profile.username || null,
        department: profile.department || null,
        organization: profile.organization || null,
      },
    }))
  } catch (err) {
    res.writeHead(502, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: err.message }))
  }
}

/** Desktop renderer (dsh-app://app) talks to loopback Host across origins. */
function applyDesktopCors(req, res) {
  const origin = String(req?.headers?.origin || '').trim()
  if (origin !== 'dsh-app://app') return false
  if (!requestIsLoopback(req)) return false
  res.setHeader('Access-Control-Allow-Origin', 'dsh-app://app')
  res.setHeader('Access-Control-Allow-Credentials', 'true')
  res.setHeader(
    'Access-Control-Allow-Headers',
    'Content-Type, X-UDS-Bridge-EmpNo, X-UDS-Bridge-Token, X-UDS-Bridge-Kind, X-UDS-Session',
  )
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  res.setHeader('Vary', 'Origin')
  return true
}

function sendJSON(res, code, data) {
  res.statusCode = code >= 200 && code < 300 ? 200 : code
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(data))
}

function localeOf(req, userContext) {
  return resolveLocale(req, userContext)
}

function sendErr(res, req, status, code, vars, userContext) {
  return sendJSON(res, status, apiError(code, localeOf(req, userContext), vars))
}

function sendOkMsg(res, req, code, vars, userContext, extra = {}) {
  return sendJSON(res, 200, { ...apiOk(code, localeOf(req, userContext), vars), ...extra })
}


/** Prefer Secure cookies only on HTTPS — http://127.0.0.1 drops Secure cookies from WS. */
function isHttpsRequest(req) {
  if (req?.socket?.encrypted) return true
  const xf = String(req?.headers?.['x-forwarded-proto'] || '').split(',')[0].trim().toLowerCase()
  return xf === 'https'
}

/**
 * UI display hints only (SEC-02) — never prove login.
 * Auth proof is UDS_SESSION / bridge bearer minted separately.
 */
function setFallbackHintCookies(req, res, extraCookies = []) {
  const fbMaxAge = 7 * 24 * 60 * 60
  const secure = isHttpsRequest(req)
  const partsUi = [
    'UDS_FALLBACK_UI=administrator',
    `Max-Age=${fbMaxAge}`,
    'Path=/',
    'SameSite=Lax',
  ]
  if (secure) partsUi.push('Secure')
  const list = [partsUi.join('; '), ...extraCookies]
  res.setHeader('Set-Cookie', list)
}

async function handleFallbackLogin(req, res) {
  if (!_loginLimiter.allow(clientKey(req))) {
    audit({ action: 'fallback_login', decision: 'deny', reasonCode: 'rate_limited' })
    return sendErr(res, req, 429, 'rate_limited')
  }
  let body
  try {
    body = await readBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
  } catch (err) {
    return sendErr(res, req, err.statusCode || 413, err.code || 'payload_too_large')
  }
  let parsed
  try { parsed = JSON.parse(body) } catch { parsed = {} }

  const { username, password } = parsed
  const ip = req.socket?.remoteAddress || 'unknown'

  if (!username || !password) {
    return sendErr(res, req, 400, 'username_password_required')
  }
  if (username !== 'administrator') {
    // 不泄露"administrator"是唯一用户名
    audit({ action: 'fallback_login', decision: 'deny', reasonCode: 'invalid_credentials' })
    return sendErr(res, req, 401, 'invalid_credentials')
  }

  const verifiedGeneration = _rolesStore.getFallbackCredVersion()
  let passwordOk
  try { passwordOk = await _rolesStore.verifyFallbackAsync(password, ip) } catch (err) {
    return sendErr(res, req, err.code === 'kdf_busy' ? 429 : 503, err.code || 'roles_persist_failed')
  }
  if (!passwordOk || verifiedGeneration !== _rolesStore.getFallbackCredVersion()) {
    audit({ action: 'fallback_login', decision: 'deny', reasonCode: 'invalid_credentials' })
    return sendErr(res, req, 401, 'invalid_credentials')
  }

  // 登录成功：签发随机本地会话；fallback UI cookie 仅提示，不能单独重建登录
  const empNo = 'administrator'
  const userContext = {
    empNo,
    username: 'Fallback Administrator',
    isAuthenticated: true,
    role: 'fallback_admin',
    authMode: 'fallback-password',
    fallbackCredVersion: verifiedGeneration,
    authenticatedAt: new Date().toISOString(),
    lastActiveAt: new Date().toISOString(),
  }
  const { bearer, bridge } = await mintLoginSession(empNo, userContext, 'fallback')
  await ensureUserWorkspace(empNo)

  setFallbackHintCookies(req, res)
  appendSessionCookie(req, res, bearer)
  audit({ action: 'fallback_login', decision: 'allow', actor: empNo })

  sendOkMsg(res, req, 'fallback_login', null, {
    empNo,
    username: userContext.username,
    isAuthenticated: true,
    role: 'fallback_admin',
  }, {
    success: true,
    empNo,
    role: 'fallback_admin',
    bridge,
  })
}

/**
 * Bind empNo+SSO token → session + bridge (and Set-Cookie when host supports it).
 * Used after QR login on Desktop where document.cookie / Set-Cookie are no-ops.
 */
async function handleBridgeBind(req, res) {
  let body
  try {
    body = await readBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
  } catch (err) {
    return sendErr(res, req, err.statusCode || 413, err.code || 'payload_too_large')
  }
  let parsed
  try { parsed = JSON.parse(body) } catch { parsed = {} }
  const empNo = String(parsed.empNo || parsed.account || '').trim()
  const token = String(parsed.token || parsed.authValue || '').trim()
  if (!empNo || !token) {
    return sendErr(res, req, 400, 'key_required')
  }
  if (!_authMiddleware?.verifyEmpNoAndToken) {
    return sendErr(res, req, 503, 'config_not_ready')
  }
  const profile = await _authMiddleware.verifyEmpNoAndToken(empNo, token)
  if (!profile) {
    return sendErr(res, req, 401, 'invalid_credentials')
  }
  const now = new Date().toISOString()
  const userContext = {
    empNo: profile.empNo || empNo,
    userId: profile.empNo || empNo,
    username: profile.username || empNo,
    displayName: profile.username || empNo,
    department: profile.department || '',
    organization: profile.organization || profile.department || '',
    email: profile.email || '',
    phone: profile.phone || '',
    token,
    isAuthenticated: true,
    authMode: 'token+profile',
    authenticatedAt: now,
    lastActiveAt: now,
    sessionCreatedAt: now,
  }
  const id = userContext.empNo
  let role
  try {
    role = await _authMiddleware.resolveRoleOnLogin(id)
  } catch (err) {
    return sendErr(res, req, 403, err?.code || 'bootstrap_required')
  }
  const { bearer, bridge } = await mintLoginSession(id, userContext, 'uds', token)
  await ensureUserWorkspace(id)

  // Local session cookie is the auth proof; portal cookies are upstream leftovers only.
  const secure = isHttpsRequest(req)
  const maxAge = Math.floor(INTERNAL.session.cookieMaxAge / 1000)
  const cookieParts = (name, value, httpOnly) => {
    const parts = [
      `${name}=${encodeURIComponent(value)}`,
      `Max-Age=${maxAge}`,
      'Path=/',
      'SameSite=Lax',
    ]
    if (httpOnly) parts.push('HttpOnly')
    if (secure) parts.push('Secure')
    return parts.join('; ')
  }
  res.setHeader('Set-Cookie', [
    buildSessionCookie(bearer, maxAge, { secure }),
    cookieParts(INTERNAL.cookieEmpNo, id, false),
  ])

  sendOkMsg(res, req, 'fallback_login', null, {
    empNo: id,
    username: userContext.username,
    displayName: userContext.displayName,
    department: userContext.department,
    isAuthenticated: true,
    role,
  }, {
    success: true,
    empNo: id,
    role,
    bridge,
  })
}

/**
 * Decrypt UDS_AUTH_LOCAL_ADMIN_BOX with operator passphrase → admin session.
 * Env ciphertext alone never grants login.
 */
async function handleLocalAdminUnlock(req, res) {
  if (!isLocalAdminBoxConfigured()) {
    return sendErr(res, req, 404, 'local_admin_not_configured')
  }
  const ip = req.socket?.remoteAddress || 'unknown'
  if (!allowUnlockAttempt(ip)) {
    audit({ action: 'local_admin_unlock', decision: 'deny', reasonCode: 'rate_limited' })
    return sendErr(res, req, 429, 'rate_limited')
  }

  let body
  try {
    body = await readBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
  } catch (err) {
    return sendErr(res, req, err.statusCode || 413, err.code || 'payload_too_large')
  }
  let parsed
  try { parsed = JSON.parse(body) } catch { parsed = {} }
  const key = String(parsed.key || parsed.passphrase || parsed.password || '').trim()
  if (!key) {
    return sendErr(res, req, 400, 'key_required')
  }

  let opened
  try { opened = await openLocalAdminBoxAsync(readLocalAdminBox(), key) } catch (err) {
    return sendErr(res, req, err.code === 'kdf_busy' ? 429 : 400, err.code || 'decrypt_failed')
  }
  if (!opened.ok) {
    audit({ action: 'local_admin_unlock', decision: 'deny', reasonCode: 'decrypt_failed' })
    return sendErr(res, req, 401, 'decrypt_failed')
  }

  const empNo = opened.empNo
  const userContext = buildLocalAdminUserContext()
  const { bearer, bridge } = await mintLoginSession(empNo, userContext, 'sealed_box')
  await ensureUserWorkspace(empNo)
  audit({ action: 'local_admin_unlock', decision: 'allow', actor: empNo })

  const fakeRes = {
    headersSent: false,
    _cookies: [],
    getHeader(name) {
      if (String(name).toLowerCase() === 'set-cookie') return this._cookies
      return undefined
    },
    setHeader(name, value) {
      if (String(name).toLowerCase() === 'set-cookie') {
        this._cookies = Array.isArray(value) ? value : [value]
      }
    },
  }
  appendLocalAdminCookie(fakeRes, req)
  setFallbackHintCookies(req, res, fakeRes._cookies)
  appendSessionCookie(req, res, bearer)

  sendOkMsg(res, req, 'local_admin_unlock', null, {
    empNo,
    username: userContext.username || 'Local Administrator',
    isAuthenticated: true,
    role: 'fallback_admin',
  }, {
    success: true,
    empNo,
    role: 'fallback_admin',
    bridge,
  })
}

/** Legacy install-root runtime path (pre-0.3.6); prefer profile data dir. */
const LEGACY_RUNTIME_CONFIG_FILE = resolve(__dirname, '..', 'config.runtime.json')
const LEGACY_PLUGIN_ROOT = resolve(__dirname, '..')
let _runtimeConfigFile = LEGACY_RUNTIME_CONFIG_FILE

function runtimeConfigPath(dataDir) {
  return dataDir ? resolve(dataDir, 'config.runtime.json') : LEGACY_RUNTIME_CONFIG_FILE
}

/**
 * F05: copy 0.3.5 install-root state into the profile data dir once.
 * Refuses silent empty bootstrap when legacy security state exists.
 */
async function migrateLegacyStateIfNeeded(dataDir, logger) {
  return migrateState(dataDir, LEGACY_PLUGIN_ROOT, logger)
}

function validateConfigPatch(partial) {
  const err = (code) => {
    const e = new Error(code)
    e.code = code
    return e
  }
  if (partial == null || typeof partial !== 'object' || Array.isArray(partial)) {
    throw err('invalid_config')
  }
  // Reject unknown security-sensitive fields being smuggled in.
  const allowed = new Set([
    'uacBaseUrl',
    'userSearchUrl',
    'loginSystemCode',
    'originSystemCode',
    'workspaceRoot',
    'retainSkillCredentialsOnLogout',
    'skillCredentialTtlSeconds',
    'outboundAllowedHosts',
    'initialAdminEmpNo',
    'allowOpenRegistration',
    'allowRawAgentToken',
    'trustedHosts',
  ])
  for (const k of Object.keys(partial)) {
    if (!allowed.has(k)) throw err('unknown_config_field')
  }
  const checkHttpsUrl = (v, code) => {
    if (v === undefined) return
    const s = String(v).trim()
    if (!s) throw err(code)
    let u
    try { u = new URL(s) } catch { throw err(code) }
    if (u.protocol !== 'https:') throw err(code)
  }
  checkHttpsUrl(partial.uacBaseUrl, 'invalid_uac_url')
  checkHttpsUrl(partial.userSearchUrl, 'invalid_user_search_url')
  if (partial.workspaceRoot !== undefined && String(partial.workspaceRoot).trim()) {
    const root = String(partial.workspaceRoot).trim()
    if (!isAbsolute(root)) throw err('invalid_workspace_root')
  }
  if (partial.skillCredentialTtlSeconds !== undefined) {
    const n = Number(partial.skillCredentialTtlSeconds)
    if (!Number.isFinite(n) || n < 60 || n > 30 * 24 * 60 * 60) {
      throw err('invalid_ttl')
    }
  }
  if (partial.outboundAllowedHosts !== undefined) {
    const raw = partial.outboundAllowedHosts
    const list = Array.isArray(raw)
      ? raw
      : String(raw).split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean)
    for (const h of list) {
      if (!/^[a-z0-9.-]+$/i.test(h) || h.includes('..')) throw err('invalid_outbound_host')
    }
  }
}

async function saveRuntimeConfig(partial) {
  if (!_currentConfig) {
    const err = new Error('config_not_ready')
    err.code = 'config_not_ready'
    throw err
  }
  validateConfigPatch(partial)
  const allowed = [
    'uacBaseUrl',
    'userSearchUrl',
    'loginSystemCode',
    'originSystemCode',
    'workspaceRoot',
    'retainSkillCredentialsOnLogout',
    'skillCredentialTtlSeconds',
    'outboundAllowedHosts',
    'initialAdminEmpNo',
    'allowOpenRegistration',
    'allowRawAgentToken',
    'trustedHosts',
  ]
  const next = asMutableConfig(_currentConfig)
  for (const k of allowed) {
    if (partial[k] !== undefined) {
      if (k === 'retainSkillCredentialsOnLogout' || k === 'allowOpenRegistration' || k === 'allowRawAgentToken') {
        next[k] = partial[k] === true || partial[k] === 'true'
      } else if (k === 'skillCredentialTtlSeconds') {
        next[k] = Number(partial[k])
      } else if (k === 'outboundAllowedHosts') {
        // Preserve [] / '' as deny-all; do not String([]) → "[]".
        next[k] = Array.isArray(partial[k]) ? partial[k].map(String) : String(partial[k])
      } else {
        next[k] = typeof partial[k] === 'string' ? partial[k] : String(partial[k])
      }
    }
  }
  // Persist first — only then swap memory (SEC-22). F05: write under profile data dir.
  await atomicWriteJson(_runtimeConfigFile, next, { mode: 0o600 })
  _currentConfig = next
}

// 统一入口：单个 prefix 路由 handler，内部自行分发
async function handleAllRoutes(req, res) {
  try {
    const url = new URL(req.url, 'http://localhost')
    const pathname = url.pathname.replace(/\/+$/, '') || '/'
    const method = (req.method || 'GET').toUpperCase()

    // Desktop dsh-app:// → loopback Host: answer CORS preflight before auth.
    if (pathname.startsWith('/uds-auth') && applyDesktopCors(req, res) && method === 'OPTIONS') {
      res.statusCode = 204
      res.end()
      return
    }

    // SEC-20 health: always answer readiness without auth.
    if (pathname === '/uds-auth/health' && method === 'GET') {
      const ready = _pluginReady && !_rolesStore?.loadFailed
      return sendJSON(res, ready ? 200 : 503, {
        ok: ready,
        ready,
        error: ready ? null : (_pluginReadyError || 'unready'),
      })
    }

    if (!_pluginReady) {
      return sendJSON(res, 503, {
        ...apiError('plugin_unready', localeOf(req)),
        detail: _pluginReadyError || 'initializing',
      })
    }

    // A09/SEC-19: Host trust on all methods (incl. GET qr-start); Origin/CT on mutating.
    const isMutating = !['GET', 'HEAD', 'OPTIONS'].includes(method)
    const trustedHostsFn = () => {
      const raw = _currentConfig?.trustedHosts
      if (raw == null || raw === '') return []
      if (Array.isArray(raw)) return raw.map(String)
      return String(raw).split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean)
    }
    const originCheck = checkRequestOrigin(req, { trustedHosts: trustedHostsFn })
    if (!originCheck.ok) {
      return sendJSON(res, 403, { ...apiError('origin_forbidden', localeOf(req)), reason: originCheck.reason })
    }
    if (isMutating) {
      if (pathname.startsWith('/uds-auth/api/') || pathname === '/uds-auth/outbound') {
        const ct = requireJsonContentType(req)
        if (!ct.ok) {
          return sendJSON(res, 415, { ...apiError('content_type', localeOf(req)), reason: ct.reason })
        }
      }
    }

    // SEC-01: generic static file routes removed (path traversal).

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

    // 用户信息代理（T03: POST body/headers；GET 仅 headers，禁止 query token）
    if (pathname === '/uds-auth/user-info' && (method === 'GET' || method === 'POST')) {
      return await handleUserInfo(req, res)
    }

    // Skill / agent：本机凭证与出站代理（loopback-only）
    if (pathname === '/uds-auth/agent-credentials' && (method === 'GET' || method === 'POST')) {
      if (!_agentAuthHandlers) {
        res.statusCode = 503
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify(apiError('skill_credentials_not_ready', localeOf(req))))
        return
      }
      return await _agentAuthHandlers.handleAgentCredentials(req, res)
    }
    if (pathname === '/uds-auth/outbound' && method === 'POST') {
      if (!_agentAuthHandlers) {
        res.statusCode = 503
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify(apiError('outbound_not_ready', localeOf(req))))
        return
      }
      return await _agentAuthHandlers.handleOutbound(req, res)
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
    res.end(JSON.stringify({ ...apiError('not_found', localeOf(req)), path: pathname }))
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
    if (url === '/api/local-admin/status' && method === 'GET') {
      return sendJSON(res, 200, {
        enabled: isLocalAdminBoxConfigured(),
        env: LOCAL_ADMIN_BOX_ENV,
      })
    }
    if (url === '/api/local-admin/unlock' && method === 'POST') {
      await handleLocalAdminUnlock(req, res)
      return
    }
    // QR / SSO → bridge (Desktop); also refreshes cookies when the host supports them.
    if (url === '/api/bridge/bind' && method === 'POST') {
      await handleBridgeBind(req, res)
      return
    }

    // 以下都需要登录态
    if (!ctx2.empNo) {
      return sendErr(res, req, 401, 'not_logged_in', null, ctx2.userContext)
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
    if (url === '/api/me/view-all-sessions' && method === 'POST') {
      await _apiHandlers.setViewAllSessions(ctx2); return
    }

    // T01: short-TTL one-time WS handshake ticket (never put long-lived bearer in WS URL).
    if (url === '/api/ws-ticket' && method === 'POST') {
      const extracted = await extractSessionBearerAsync(req, {
        sessionBridge: _sessionBridge,
        isLiveBearer: async (b) => !!(await _sessionStore?.getByBearer(b)),
      })
      const bearer = extracted?.bearer
      if (!bearer || !_sessionBridge) {
        return sendErr(res, req, 401, 'not_logged_in', null, ctx2.userContext)
      }
      try {
        const minted = _sessionBridge.mintWsTicket({
          empNo: ctx2.empNo,
          bearer,
          ttlMs: 60_000,
        })
        return sendJSON(res, 200, {
          ticket: minted.ticket,
          expiresAt: minted.expiresAt,
          expiresIn: minted.expiresIn,
        })
      } catch (err) {
        return sendErr(res, req, 400, err.message || 'ws_ticket_failed', null, ctx2.userContext)
      }
    }

    // 配置端点 (admin / super_admin：canAccessSettings)
    if (url === '/api/config' && method === 'GET') {
      if (!requirePermission(ctx2, 'canAccessSettings')) {
        return sendErr(res, req, 403, 'forbidden_settings', null, ctx2.userContext)
      }
      sendJSON(res, 200, { config: _currentConfig })
      return
    }
    if (url === '/api/config' && method === 'POST') {
      if (!requirePermission(ctx2, 'canAccessSettings')) {
        return sendErr(res, req, 403, 'forbidden_settings', null, ctx2.userContext)
      }
      let body
      try {
        body = await readBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
      } catch (err) {
        return sendErr(res, req, err.statusCode || 413, err.code || 'payload_too_large', null, ctx2.userContext)
      }
      let parsed
      try { parsed = JSON.parse(body) } catch { parsed = {} }
      try {
        await saveRuntimeConfig(parsed)
        audit({
          action: 'config_save',
          decision: 'allow',
          actor: ctx2.empNo,
          meta: { keys: Object.keys(parsed || {}) },
        })
        sendOkMsg(res, req, 'config_saved', null, ctx2.userContext)
      } catch (err) {
        const code = err?.code || err?.message
        audit({
          action: 'config_save',
          decision: 'deny',
          actor: ctx2.empNo,
          reasonCode: code,
        })
        if (code === 'config_not_ready') {
          sendErr(res, req, 400, 'config_not_ready', null, ctx2.userContext)
        } else if (typeof code === 'string' && !code.includes(' ')) {
          sendErr(res, req, 400, code, null, ctx2.userContext)
        } else {
          sendJSON(res, 400, { error: 'request_failed', message: err.message })
        }
      }
      return
    }

    // 基础端点
    if (url === '/api/me' && method === 'GET') {
      if (ctx2.empNo) {
        // Never block login badge / ACL on workspaceRegistry (can wait up to 30s).
        // Serve cached mapping immediately; provision in background.
        try {
          ctx2.provisionedWorkspace = _userWorkspaces?.get?.(ctx2.empNo) || null
        } catch {
          ctx2.provisionedWorkspace = null
        }
        void ensureUserWorkspace(ctx2.empNo).catch(() => {})
      }
      await _apiHandlers.getCurrentUser(ctx2); return
    }
    if (url === '/api/logout' && method === 'POST') {
      await _apiHandlers.logout(ctx2); return
    }

    // SEC-07: unknown API → 404 (do not echo userContext/token)
    sendJSON(res, 404, { error: 'not_found' })
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
      // Validation + assign happen inside hooks.setSource (F04).
      hooks.setSource?.(current)
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
    const settings = settingsCtx.settings
    if (typeof settings?.installSection === 'function') {
      ctx.logger?.info?.('[uds-auth] registering settings panel (new API)')
      settings.installSection(ctx, UDS_AUTH_SETTINGS_NAMESPACE, ConfigSchema, entry, hooksArg)
      return
    }
    // DSH ≥0.1.7 / 0.2.0 — Config projection via describe() (no installSection).
    const describeRows = (describe) => {
      if (typeof describe !== 'function') return []
      try {
        const raw = describe()
        if (Array.isArray(raw)) return raw
        if (raw && typeof raw === 'object' && Array.isArray(raw.namespaces)) return raw.namespaces
      } catch { /* settling */ }
      return []
    }
    const readLive = () => {
      const row = describeRows(settings?.describe).find((item) => item.ns === UDS_AUTH_SETTINGS_NAMESPACE)
      if (row?.value !== null && typeof row?.value === 'object' && !Array.isArray(row.value)) {
        return asMutableConfig({ ...entry, ...row.value })
      }
      return asMutableConfig(entry)
    }
    hooksArg.setSource(readLive)
    hooksArg.onChange()
    let last = JSON.stringify(readLive())
    const timer = setInterval(() => {
      const next = readLive()
      const fingerprint = JSON.stringify(next)
      if (fingerprint === last) return
      last = fingerprint
      hooksArg.onChange()
    }, 2_000)
    settingsCtx.effect(() => () => clearInterval(timer), 'uds-auth: settings describe poll')
    ctx.logger?.info?.('[uds-auth] following settings via describe() (DSH ≥0.1.7 path)')
  })
}


let _workspaceRegistry = null
let _workspaceRegistryWaiters = []

function notifyWorkspaceRegistryReady(registry) {
  _workspaceRegistry = registry || null
  const waiters = _workspaceRegistryWaiters.splice(0)
  for (const w of waiters) {
    try { clearTimeout(w.timer) } catch { /* ignore */ }
    try { w.resolve(_workspaceRegistry) } catch { /* ignore */ }
  }
}

/** Wait until workspaceRegistry inject fires (or timeout). */
function whenWorkspaceRegistry(timeoutMs = 2500) {
  if (_workspaceRegistry) return Promise.resolve(_workspaceRegistry)
  return new Promise((resolve) => {
    const entry = {
      resolve,
      timer: setTimeout(() => {
        const i = _workspaceRegistryWaiters.indexOf(entry)
        if (i >= 0) _workspaceRegistryWaiters.splice(i, 1)
        resolve(_workspaceRegistry || null)
      }, timeoutMs),
    }
    _workspaceRegistryWaiters.push(entry)
  })
}

async function ensureUserWorkspace(empNo) {
  if (!_userWorkspaces) return null
  try {
    let registry = _workspaceRegistry
    if (!registry) {
      registry = await whenWorkspaceRegistry(2500)
    }
    const root = _currentConfig?.workspaceRoot
    if (!registry) {
      console.warn(
        '[uds-auth] workspaceRegistry still unavailable after wait; mkdir only under',
        root || '(default $DSH_HOME/user-workspaces)',
      )
    }
    return await _userWorkspaces.ensureUserWorkspace(
      { workspaceRegistryHandle: registry },
      root,
      empNo,
    )
  } catch (err) {
    console.warn('[uds-auth] ensureUserWorkspace failed:', err.message)
    return null
  }
}

async function rebindPendingUserWorkspaces() {
  if (!_userWorkspaces || !_workspaceRegistry) return
  try {
    const users = _userWorkspaces._map
    if (!users || typeof users.keys !== 'function') return
    for (const empNo of users.keys()) {
      const row = users.get(empNo)
      if (row && row.workspaceId) continue
      try { await ensureUserWorkspace(empNo) } catch { /* ignore */ }
    }
  } catch (err) {
    console.warn('[uds-auth] rebindPendingUserWorkspaces failed:', err.message)
  }
}

export async function apply(ctx, config = {}) {
  let source = () => mergeConfig(config)
  _currentConfig = asMutableConfig(source())
  _logger = ctx.logger || console

  ctx.logger?.info?.('[uds-auth] Loading...')

  installSettingsSection(ctx, source(), {
    setSource: (current) => {
      const next = asMutableConfig(typeof current === 'function' ? current() : current)
      // F04: same HTTPS/field validation as config API / startup.
      try {
        validateConfigPatch({
          uacBaseUrl: next.uacBaseUrl,
          userSearchUrl: next.userSearchUrl,
          outboundAllowedHosts: next.outboundAllowedHosts,
          skillCredentialTtlSeconds: next.skillCredentialTtlSeconds,
          workspaceRoot: next.workspaceRoot || undefined,
          trustedHosts: next.trustedHosts,
        })
      } catch (err) {
        ctx.logger?.warn?.('[uds-auth] settings rejected: %s', err.code || err.message)
        throw err
      }
      source = typeof current === 'function' ? current : () => next
      _currentConfig = next
    },
    onChange: () => {
      const next = asMutableConfig(source())
      try {
        validateConfigPatch({
          uacBaseUrl: next.uacBaseUrl,
          userSearchUrl: next.userSearchUrl,
          outboundAllowedHosts: next.outboundAllowedHosts,
          skillCredentialTtlSeconds: next.skillCredentialTtlSeconds,
          workspaceRoot: next.workspaceRoot || undefined,
          trustedHosts: next.trustedHosts,
        })
      } catch (err) {
        ctx.logger?.warn?.('[uds-auth] settings onChange rejected: %s', err.code || err.message)
        throw err
      }
      _currentConfig = next
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
  _pluginReady = false
  _pluginReadyError = 'initializing'
  try {
    const existingGateway = tryGet(ctx, 'typertGateway')
    if (existingGateway) assertGatewayContract(existingGateway)
    const { createSessionStore } = await import('./session/factory.js')
    const { createAuthMiddleware } = await import('./middleware/auth-middleware.js')
    const { createApiHandlers } = await import('./api.js')
    const { RolesStore } = await import('./roles.js')
    const { SessionAclStore } = await import('./session-acl.js')
    const { UserWorkspaceStore } = await import('./workspace-provision.js')
    const { patchWebServerWithIdentity, resolveIdentityFromRequest, resolveIdentityFromRequestSync, installDshAcl } = await import('./dsh-acl.js')
    const { SkillCredentialCache } = await import('./skill-credentials.js')
    const { createAgentAuthHandlers } = await import('./agent-auth.js')

    _pluginCtx = ctx
    _currentConfig = asMutableConfig(config)

    // A11/F05: resolve profile data dir first, migrate legacy install-root state, then load runtime.
    const pluginDataDir = resolvePluginDataDir(_currentConfig)
    await mkdir(pluginDataDir, { recursive: true, mode: 0o700 })
    await protectProfileDirectory(pluginDataDir)
    ctx.logger?.info?.('[uds-auth] profile data dir: %s', pluginDataDir)
    await migrateLegacyStateIfNeeded(pluginDataDir, ctx.logger || console)
    await protectProfileDirectory(pluginDataDir)
    _runtimeConfigFile = runtimeConfigPath(pluginDataDir)

    try {
      const raw = await readFile(_runtimeConfigFile, 'utf-8')
      const rt = JSON.parse(raw)
      if (rt && typeof rt === 'object') {
        _currentConfig = { ..._currentConfig, ...rt }
      }
    } catch {
      // Fall back to legacy install-root runtime once if profile copy missing.
      try {
        const raw = await readFile(LEGACY_RUNTIME_CONFIG_FILE, 'utf-8')
        const rt = JSON.parse(raw)
        if (rt && typeof rt === 'object') {
          _currentConfig = { ..._currentConfig, ...rt }
        }
      } catch { /* runtime config optional */ }
    }

    // A09: same HTTPS + field validation as config POST / settings.
    try {
      validateConfigPatch({
        uacBaseUrl: _currentConfig.uacBaseUrl,
        userSearchUrl: _currentConfig.userSearchUrl,
        outboundAllowedHosts: _currentConfig.outboundAllowedHosts,
        skillCredentialTtlSeconds: _currentConfig.skillCredentialTtlSeconds,
        workspaceRoot: _currentConfig.workspaceRoot || undefined,
        trustedHosts: _currentConfig.trustedHosts,
      })
    } catch (err) {
      throw new Error(`invalid_startup_config:${err.code || err.message}`)
    }

    // Normalize skill-related config after merge
    if (_currentConfig.retainSkillCredentialsOnLogout === undefined) {
      _currentConfig.retainSkillCredentialsOnLogout = CONFIG_DEFAULTS.retainSkillCredentialsOnLogout
    } else {
      _currentConfig.retainSkillCredentialsOnLogout =
        _currentConfig.retainSkillCredentialsOnLogout === true
        || _currentConfig.retainSkillCredentialsOnLogout === 'true'
    }
    if (!_currentConfig.skillCredentialTtlSeconds) {
      _currentConfig.skillCredentialTtlSeconds = CONFIG_DEFAULTS.skillCredentialTtlSeconds
    }
    // R05: only default when field absent — empty string / [] means deny-all.
    if (_currentConfig.outboundAllowedHosts === undefined || _currentConfig.outboundAllowedHosts === null) {
      _currentConfig.outboundAllowedHosts = CONFIG_DEFAULTS.outboundAllowedHosts
    }

    _sessionStore = await createSessionStore(INTERNAL.session, {
      file: resolve(pluginDataDir, 'sessions.json'),
      dataDir: pluginDataDir,
      logger: ctx.logger || console,
    })
    const ttlMs = Math.max(60, Number(_currentConfig.skillCredentialTtlSeconds) || CONFIG_DEFAULTS.skillCredentialTtlSeconds) * 1000
    _skillCredentials = new SkillCredentialCache({
      file: resolve(pluginDataDir, 'skill-credentials.json'),
      dataDir: pluginDataDir,
      ttlMs,
      logger: ctx.logger || console,
    })
    await _skillCredentials.init()

    const rolesFile = resolve(pluginDataDir, 'roles.json')
    _rolesStore = new RolesStore({ rolesFile })
    await _rolesStore.init()
    if (_rolesStore.loadFailed) {
      throw new Error('roles_store_corrupt')
    }
    logLocalAdminStatus(ctx.logger || console)

    _sessionBridge = new SessionBridgeStore({
      file: resolve(pluginDataDir, 'session-bridge.json'),
      ttlMs: INTERNAL.session.cookieMaxAge,
    })
    await _sessionBridge.init()
    ctx.logger?.info?.('[uds-auth] session bridge ready (cookie + header dual path)')

    _sessionAcl = new SessionAclStore({ ownersFile: resolve(pluginDataDir, 'session-owners.json') })
    await _sessionAcl.init()
    if (_sessionAcl.loadFailed) {
      throw new Error('session_owners_corrupt')
    }

    _userWorkspaces = new UserWorkspaceStore({ mapFile: resolve(pluginDataDir, 'user-workspaces.json') })
    await _userWorkspaces.init()

    const { TaskCapabilityStore } = await import('./task-capability.js')
    _taskCapabilities = new TaskCapabilityStore({ defaultTtlSeconds: 3600 })

    const rememberSkillCreds = (empNo, token) => {
      try { _skillCredentials?.set(empNo, token) } catch { /* ignore */ }
    }

    _authMiddleware = createAuthMiddleware({
      get userSearchUrl() { return _currentConfig?.userSearchUrl },
      getInitialAdminEmpNo: () => _currentConfig?.initialAdminEmpNo || process.env.UDS_AUTH_INITIAL_ADMIN || '',
      getAllowOpenRegistration: () => _currentConfig?.allowOpenRegistration !== false,
      udsAuth: {
        get baseUrl() { return _currentConfig?.uacBaseUrl },
        get systemCode() { return _currentConfig?.loginSystemCode },
        get userSearchUrl() { return _currentConfig?.userSearchUrl },
        empNoHeader: INTERNAL.empNoHeader,
        authValueHeader: INTERNAL.authValueHeader,
      },
      session: INTERNAL.session,
    }, _sessionStore, _rolesStore, {
      onSkillCredentials: rememberSkillCreds,
      sessionBridge: _sessionBridge,
    })

    // Revalidate QR-authenticated sessions against the UDS department profile.
    // The session store still enforces the independent seven-day absolute limit.
    const udsSessionCheckTimer = setInterval(async () => {
      let sessions
      try {
        sessions = await _sessionStore.listUdsSessionsForValidation()
      } catch (err) {
        ctx.logger?.warn?.('[uds-auth] failed to enumerate UDS sessions for validation:', err?.message || err)
        return
      }
      for (const session of sessions) {
        try {
          if (!session.token || !await _authMiddleware.verifyEmpNoAndToken(session.empNo, session.token)) {
            await _sessionStore.revokeSession(session.sessionId)
            ctx.logger?.info?.('[uds-auth] UDS session revoked after profile validation failed for %s', session.empNo)
          }
        } catch (err) {
          await _sessionStore.revokeSession(session.sessionId).catch(() => {})
          ctx.logger?.info?.('[uds-auth] UDS session revoked after profile validation error for %s: %s', session.empNo, err?.message || err)
        }
      }
    }, 6 * 60 * 60 * 1000)
    udsSessionCheckTimer.unref?.()
    ctx.effect?.(() => () => clearInterval(udsSessionCheckTimer), 'uds-auth: UDS session validation')

    _apiHandlers = createApiHandlers(
      { session: INTERNAL.session },
      _sessionStore,
      _rolesStore,
      {
        skillCredentials: _skillCredentials,
        retainSkillCredentialsOnLogout: () => _currentConfig?.retainSkillCredentialsOnLogout !== false,
        sessionBridge: _sessionBridge,
        revokeTaskCapabilitiesForEmpNo: (empNo) => _taskCapabilities?.revokeEmpNo(empNo) || 0,
      },
    )

    function parseOutboundHosts() {
      const raw = _currentConfig?.outboundAllowedHosts
      // R05: undefined → packaged defaults; '' / [] → deny all (do not revive defaults).
      if (raw === undefined || raw === null) {
        return String(CONFIG_DEFAULTS.outboundAllowedHosts)
          .split(/[,;\s]+/)
          .map((s) => s.trim())
          .filter(Boolean)
      }
      if (Array.isArray(raw)) return raw.map(String).map((s) => s.trim()).filter(Boolean)
      const s = String(raw).trim()
      if (!s) return []
      return s.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean)
    }

    async function resolveCredentialsForEmpNo(empNo) {
      if (!empNo) return null
      const row = _skillCredentials?.get(empNo)
      if (!row?.token) return null
      return { empNo: row.empNo, token: row.token, updatedAt: row.updatedAt }
    }

    async function resolveCredentialsForSession(sessionId) {
      if (!sessionId) return null
      const empNo = _sessionAcl?.getOwner(sessionId) || null
      if (!empNo) return null
      return resolveCredentialsForEmpNo(empNo)
    }

    _agentAuthHandlers = createAgentAuthHandlers({
      resolveCredentialsForSession,
      getSessionOwner: (sessionId) => _sessionAcl?.getOwner(sessionId) || null,
      resolveCallerSession: async (req) => {
        const extracted = await extractSessionBearerAsync(req, {
          sessionBridge: _sessionBridge,
          isLiveBearer: async (b) => !!(await _sessionStore?.getByBearer(b)),
        })
        if (!extracted?.bearer) return null
        const session = await _sessionStore.getByBearer(extracted.bearer)
        if (!session?.empNo) return null
        return { empNo: session.empNo, sessionId: session.sessionId }
      },
      allowRawTokenResponse: () => _currentConfig?.allowRawAgentToken === true,
      empNoHeader: INTERNAL.empNoHeader,
      authValueHeader: INTERNAL.authValueHeader,
      outboundHosts: () => parseOutboundHosts(),
      sessionBridge: _sessionBridge,
      taskCapabilities: _taskCapabilities,
      isAccountActive: (empNo) => !(_rolesStore?.isDisabled?.(empNo)),
    })

    const identityDeps = {
      sessionStore: _sessionStore,
      rolesStore: _rolesStore,
      sessionBridge: _sessionBridge,
    }
    const resolveIdentity = (req) => resolveIdentityFromRequest(req, identityDeps)
    const resolveIdentitySync = (req) => resolveIdentityFromRequestSync(req, identityDeps)

    const patchServer = (server) => {
      patchWebServerWithIdentity(server, resolveIdentity, resolveIdentitySync, (req, upgrade) => {
        const gateway = tryGet(ctx, 'typertGateway')
        const pathname = new URL(req.url || '/', 'http://uds.local').pathname
        if (pathname.startsWith('/api/') && gateway && !gateway.__udsGatewayPolicy?.installed) {
          return { ok: false, reason: 'gateway_acl_not_ready' }
        }
        return checkRequestOrigin(req, { upgrade, trustedHosts: () => {
          const raw = _currentConfig?.trustedHosts
          return Array.isArray(raw) ? raw : String(raw || '').split(/[,;\s]+/).filter(Boolean)
        } })
      })
    }
    const present = tryGet(ctx, 'webServer')
    if (present) patchServer(present)
    ctx.inject(['webServer'], (wctx) => {
      patchServer(wctx.webServer)
    })

    ctx.inject(['workspaceRegistry'], (wctx) => {
      notifyWorkspaceRegistryReady(wctx.workspaceRegistry)
      ctx.logger?.info?.('[uds-auth] workspaceRegistry ready')
      void rebindPendingUserWorkspaces()
    })

    installDshAcl(ctx, {
      sessionAcl: _sessionAcl,
      userWorkspaces: _userWorkspaces,
      getWorkspaceRoot: () => _currentConfig?.workspaceRoot,
      getRolesStore: () => _rolesStore,
      getSessionStore: () => _sessionStore,
      ensureUserWorkspace,
      getWorkspaceRegistry: () => _workspaceRegistry,
    })

    const { resolveWorkspaceRoot } = await import('./workspace-provision.js')
    const { join } = await import('node:path')

    function displayNameOf(identity) {
      const uc = identity?.userContext || {}
      return String(
        uc.displayName || uc.userName || uc.username || uc.name || identity?.empNo || '',
      ).trim() || (identity?.empNo || '')
    }

    const udsAuth = {
      runAsHost,
      /**
       * R06: mint a short-lived task capability for skill/cron (Host-trusted callers).
       * Inject as env UDS_TASK_CAPABILITY or header X-UDS-Task-Capability.
       */
      mintTaskCapability(input) {
        if (!_taskCapabilities) throw new Error('task_capabilities_unavailable')
        const sid = String(input?.dshSessionId || '').trim()
        const owner = sid ? _sessionAcl?.getOwner(sid) : null
        if (!owner || owner !== input?.empNo || _rolesStore.isDisabled(owner)) {
          throw new Error('capability_session_owner_required')
        }
        return _taskCapabilities.mint({ ...input, empNo: owner, dshSessionId: sid,
          audience: 'uds-auth-agent', scopes: input?.scopes || ['outbound'], mintedBy: 'host:udsAuth' })
      },
      revokeTaskCapabilitiesForEmpNo(empNo) {
        return _taskCapabilities?.revokeEmpNo(empNo) || 0
      },
      async resolveRequestIdentity(req) {
        const identity = await resolveIdentity(req)
        if (!identity?.empNo) return null
        return {
          empNo: identity.empNo,
          role: identity.role,
          permissions: identity.permissions || {},
          displayName: displayNameOf(identity),
          kind: identity.kind || 'uds',
          userContext: identity.userContext || null,
        }
      },
      resolveRequestIdentitySync(req) {
        const identity = resolveIdentitySync(req)
        if (!identity?.empNo) return null
        return {
          empNo: identity.empNo,
          role: identity.role,
          permissions: identity.permissions || {},
          displayName: displayNameOf(identity),
          kind: identity.kind || 'uds',
          userContext: identity.userContext || null,
        }
      },
      canViewAllJobs(identity) {
        const empNo = identity?.empNo || identity?.userContext?.empNo
        if (empNo && _rolesStore?.resolvePermissions) {
          return !!_rolesStore.resolvePermissions(empNo, identity?.role).canViewAllSessions
        }
        return !!identity?.permissions?.canViewAllSessions
      },
      getRole(empNo) {
        const id = String(empNo || '').trim()
        if (!id || id.startsWith('__')) return 'user'
        return _rolesStore?.getRole?.(id) || 'user'
      },
      /**
       * Resolve role + permissions for an empNo (cron tools / fire-time cwd).
       * Does not touch request cookies — pure lookup from roles store.
       */
      resolveIdentityForEmpNo(empNo) {
        const id = String(empNo || '').trim()
        if (!id || id.startsWith('__')) return null
        const role = _rolesStore?.getRole?.(id) || 'user'
        const permissions = _rolesStore?.resolvePermissions?.(id, role)
          || computePermissions(role)
        const workspacePath = (() => {
          try {
            const row = _userWorkspaces?.get(id)
            if (row?.path) return row.path
            return join(resolveWorkspaceRoot(_currentConfig?.workspaceRoot), id)
          } catch {
            return null
          }
        })()
        return {
          empNo: id,
          role,
          permissions,
          displayName: id,
          workspacePath,
        }
      },
      getProvisionedWorkspacePath(empNo) {
        if (!empNo) return null
        const row = _userWorkspaces?.get(String(empNo))
        if (row?.path) return row.path
        return join(resolveWorkspaceRoot(_currentConfig?.workspaceRoot), String(empNo))
      },
      async ensureProvisionedWorkspace(empNo) {
        return ensureUserWorkspace(empNo)
      },
      isUserPath(empNo, candidatePath) {
        if (!_userWorkspaces) return false
        return _userWorkspaces.isUserPath(
          empNo,
          candidatePath,
          _currentConfig?.workspaceRoot,
        )
      },
      stampSessionOwner(sessionId, empNo) {
        if (!_sessionAcl || !sessionId || !empNo || String(empNo).startsWith('__')
          || _rolesStore.isDisabled(empNo)) return false
        return _sessionAcl.setOwner(sessionId, empNo)
      },
      getSessionOwner(sessionId) {
        return _sessionAcl?.getOwner(sessionId) || null
      },
      getGatewayInventory() {
        return runAsHost(() => {
          const gateway = tryGet(ctx, 'typertGateway')
          if (!gateway) return []
          const endpoints = new Set(gateway.collectSrcClaims?.() || [])
          for (const row of gateway.ctx?.get?.('typert')?.local?.list?.() || []) {
            endpoints.add(`${row.namespace}/${row.method}`)
          }
          const rows = [...endpoints].sort().map(endpoint => {
            const [namespace, method] = endpoint.split('/')
            const descriptor = gateway.resolveDescriptor(namespace, method, endpoint)
            return { endpoint, service: descriptor.service, policy: gatewayPolicy(descriptor), mode: descriptor.mode || 'unary',
              invocation: descriptor.invocation, parameters: descriptor.parameters.map(p => ({ name: p.name, wire: p.wire, source: p.source })) }
          })
          return [...rows, { endpoint: '$events', mode: 'stream', policy: 'authenticated-owner-filtered-events' },
            { endpoint: '$events/result', mode: 'unary', policy: 'login-session-and-agent-bound-result' }]
        })
      },
      resolveCredentialsForSession,
      resolveCredentialsForEmpNo,
      rememberSkillCredentials(empNo, token) {
        rememberSkillCreds(empNo, token)
      },
    }

    ctx.provide('udsAuth', udsAuth)
    const { createTaskEnvironment } = await import('./task-environment.js')
    ctx.inject(['shellEnv', 'webServer'], (sctx) => {
      const env = createTaskEnvironment({ getOwner: sid => _sessionAcl?.getOwner(sid),
        rolesStore: _rolesStore, capabilities: _taskCapabilities,
        getWebServer: () => tryGet(sctx, 'webServer') })
      sctx.shellEnv.register(env.contributor)
      sctx.on('tools/result', (execution, result) => { env.finish(execution, result, tryGet(sctx, 'jobs')) })
      sctx.effect(() => () => env.dispose(), 'uds-auth: task capabilities')
    })
    _pluginReady = true
    _pluginReadyError = null
    ctx.logger?.info?.('[uds-auth] Initialized (ACL + workspaces + skill credentials + udsAuth service)')
  } catch (err) {
    _pluginReady = false
    _pluginReadyError = String(err?.message || err)
    ctx.logger?.error?.('[uds-auth] Init failed: ' + _pluginReadyError)
    // SEC-20: do not silently report Host ready with open routes.
    throw err
  }
}
