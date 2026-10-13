import { UdsClient } from '../uds/client.js'
import { UdsValidator } from '../uds/validator.js'
import { ROLES } from '../roles.js'
import { searchUserByEmpNoToken } from '../uds/user-search.js'
import {
  extractSessionBearerAsync,
  extractPortalCredentials,
  buildSessionCookie,
} from '../session/request-auth.js'
import { isLocalAdminBoxConfigured } from '../local-admin.js'

/**
 * auth-middleware
 *
 * Principal only from verified local session (UDS_SESSION / bridge bearer)
 * or a fresh UAC login exchange that mints a new local session.
 *
 * UDS_FALLBACK_USER / UDS_FALLBACK_UI are display hints only — never auth.
 * empNo-keyed profile cache hits never prove authentication.
 */
export function createAuthMiddleware(config, sessionStore, rolesStore, hooks = {}) {
  const onSkillCredentials = typeof hooks.onSkillCredentials === 'function'
    ? hooks.onSkillCredentials
    : null
  const sessionBridge = hooks.sessionBridge || null
  const onSessionMinted = typeof hooks.onSessionMinted === 'function'
    ? hooks.onSessionMinted
    : null
  const udsClient = new UdsClient(config.udsAuth)
  const validatorConfig = {
    ...config.udsAuth,
    authMode: config.udsAuth?.authMode || 'token+profile',
  }
  const udsValidator = new UdsValidator(validatorConfig)
  const { slidingExpiration } = config.session
  // Read per request: cookieMaxAge follows the live sessionIdleTimeoutHours setting.
  const ttlSeconds = () => Math.floor(config.session.cookieMaxAge / 1000)
  const slidingIntervalMs = Math.max(0, Number(config.session.slidingInterval) || 0)
  const userSearchUrl = config.userSearchUrl || config.udsAuth?.userSearchUrl
  const uacBaseUrl = config.udsAuth?.baseUrl || ''
  /** R05: read live — do not freeze allowOpenRegistration at middleware create time. */
  const isOpenRegistration = () => {
    if (typeof config.getAllowOpenRegistration === 'function') {
      return config.getAllowOpenRegistration() !== false
    }
    if (typeof config.allowOpenRegistration === 'function') {
      return config.allowOpenRegistration() !== false
    }
    return config.allowOpenRegistration !== false
  }
  const resolveInitialAdmin = () => String(
    (typeof config.getInitialAdminEmpNo === 'function'
      ? config.getInitialAdminEmpNo()
      : config.initialAdminEmpNo)
      || process.env.UDS_AUTH_INITIAL_ADMIN
      || '',
  ).trim()
  const initialAdminEmpNo = resolveInitialAdmin()

  /** @param {{ onFailure?: (out: object) => void }} [opts] lets callers surface why the lookup failed */
  async function verifyEmpNoAndToken(empNo, token, opts = {}) {
    const out = await searchUserByEmpNoToken({
      userSearchUrl,
      empNo,
      token,
      empNoHeader: config.udsAuth?.empNoHeader || 'X-Emp-No',
      authValueHeader: config.udsAuth?.authValueHeader || 'X-Auth-Value',
      origin: uacBaseUrl || undefined,
    })
    if (!out.ok) {
      console.warn('[uds-auth] verifyEmpNoAndToken failed:', out)
      try { opts.onFailure?.(out) } catch { /* diagnostics only */ }
      return null
    }
    const subject = String(out.profile?.empNo || '').trim()
    if (!subject || subject !== String(empNo).trim()) {
      console.warn('[uds-auth] verifyEmpNoAndToken subject mismatch')
      try { opts.onFailure?.({ ok: false, reason: 'emp_mismatch' }) } catch { /* diagnostics only */ }
      return null
    }
    return out.profile
  }

  function applyProfile(userContext, profile, credentials) {
    userContext.userId = profile.empNo
    userContext.empNo = profile.empNo
    userContext.username = profile.username
    userContext.displayName = profile.username
    userContext.department = profile.department
    userContext.organization = profile.organization || profile.department || ''
    userContext.email = profile.email
    userContext.phone = profile.phone
    userContext.token = credentials.token
    userContext.lang = credentials.lang || userContext.lang || 'zh-CN'
    userContext.isAuthenticated = true
    userContext.authMode = 'token+profile'
    userContext.lastActiveAt = new Date().toISOString()
    return userContext
  }

  /**
   * Empty roles table cannot be claimed by arbitrary UAC users unless empNo
   * matches initialAdminEmpNo (explicit bootstrap).
   */
  async function resolveRoleOnLogin(empNo) {
    if (empNo === 'administrator') {
      return rolesStore.getRole(empNo)
    }
    // R12: disabled accounts cannot re-enter via SSO / open registration.
    if (typeof rolesStore.isDisabled === 'function' && rolesStore.isDisabled(empNo)) {
      const err = new Error('account_disabled')
      err.code = 'account_disabled'
      throw err
    }
    if (rolesStore.hasRole(empNo)) {
      return rolesStore.getRole(empNo)
    }
    const adminEmp = resolveInitialAdmin()
    if (rolesStore.isEmpty()) {
      if (adminEmp && empNo === adminEmp) {
        const { role, bootstrapped } = await rolesStore.bootstrapFirstUser(empNo)
        if (bootstrapped) {
          console.info('[uds-auth] BOOTSTRAP: ' + empNo + ' is now super_admin (initialAdminEmpNo)')
        }
        return role
      }
      const err = new Error('bootstrap_required')
      err.code = 'bootstrap_required'
      throw err
    }
    if (!isOpenRegistration()) {
      const err = new Error('registration_closed')
      err.code = 'registration_closed'
      throw err
    }
    const { role } = await rolesStore.bootstrapFirstUser(empNo)
    return role
  }

  function isHttpsRequest(req) {
    if (req?.socket?.encrypted) return true
    const xf = String(req?.headers?.['x-forwarded-proto'] || '').split(',')[0].trim().toLowerCase()
    return xf === 'https'
  }

  function classifySessionKind(session) {
    // Keep sealed_box independent of emergency-password enablement (A08).
    const mode = String(
      session?.kind
      || session?.authMode
      || session?.userData?.authMode
      || '',
    )
    if (mode.includes('local-admin') || mode === 'sealed_box' || mode === 'local_admin') {
      return 'sealed_box'
    }
    if (
      mode === 'fallback'
      || mode.includes('fallback')
      || (session?.empNo === 'administrator' && (!mode || mode === 'uds'))
    ) {
      return 'fallback'
    }
    return 'uds'
  }

  async function attachFromSession(ctx, session, { persistTouch = false, res = null, req = null } = {}) {
    const empNo = session.empNo
    if (typeof rolesStore.isDisabled === 'function' && rolesStore.isDisabled(empNo)) {
      const err = new Error('account_disabled')
      err.code = 'account_disabled'
      throw err
    }
    const kind = classifySessionKind(session)
    // A01/V25: password-fallback sessions die when emergency password is cleared.
    if (kind === 'fallback'
      && typeof rolesStore.isFallbackEnabled === 'function'
      && !rolesStore.isFallbackEnabled()) {
      const err = new Error('fallback_disabled')
      err.code = 'fallback_disabled'
      throw err
    }
    // F02/E11: sealed-box sessions require live box configuration.
    if (kind === 'sealed_box' && !isLocalAdminBoxConfigured()) {
      const err = new Error('local_admin_not_configured')
      err.code = 'local_admin_not_configured'
      throw err
    }
    // F02: reject password sessions minted before the latest rotation.
    if (kind === 'fallback' && typeof rolesStore.getFallbackCredVersion === 'function') {
      const liveVer = rolesStore.getFallbackCredVersion()
      const sessVer = session.userData?.fallbackCredVersion ?? session.fallbackCredVersion
      if (sessVer != null && Number(sessVer) !== Number(liveVer)) {
        const err = new Error('fallback_rotated')
        err.code = 'fallback_rotated'
        throw err
      }
    }
    const userContext = { ...session.userData, empNo, _sessionId: session.sessionId }
    if (persistTouch || slidingExpiration) {
      await sessionStore.touch(session.sessionId, ttlSeconds())
      userContext.lastActiveAt = new Date().toISOString()
    }
    const role = kind === 'fallback' || kind === 'sealed_box' || rolesStore.hasRole(empNo)
      ? rolesStore.getRole(empNo)
      : ROLES.USER
    if (userContext.token) {
      try { onSkillCredentials?.(empNo, userContext.token) } catch { /* ignore */ }
    }
    ctx.userContext = userContext
    ctx.empNo = empNo
    ctx.role = role
    ctx.permissions = rolesStore.resolvePermissions(empNo, role)
    ctx.sessionId = session.sessionId
    ctx.authVia = 'session'
    ctx.authKind = kind
    if (res && req && session._bearerForCookie) {
      appendSessionCookie(req, res, session._bearerForCookie)
    }
  }

  function appendSessionCookie(req, res, bearer) {
    const cookie = buildSessionCookie(bearer, ttlSeconds(), { secure: isHttpsRequest(req) })
    const prev = res.getHeader?.('Set-Cookie')
    const list = Array.isArray(prev) ? [...prev, cookie] : (prev ? [prev, cookie] : [cookie])
    res.setHeader?.('Set-Cookie', list)
  }

  async function mintSession(ctx, userContext, kind, { res, req } = {}) {
    const { sessionId, bearer, record } = await sessionStore.create(userContext, ttlSeconds())
    if (userContext.token) {
      try { onSkillCredentials?.(userContext.empNo, userContext.token) } catch { /* ignore */ }
    }
    try { await sessionStore.setProfile?.(userContext.empNo, userContext) } catch { /* ignore */ }
    onSessionMinted?.({ sessionId, bearer, empNo: userContext.empNo, kind })
    const session = { ...record, _bearerForCookie: bearer }
    await attachFromSession(ctx, session, { res, req })
    return { sessionId, bearer }
  }

  async function authMiddleware(ctx, next) {
    const { req, res } = ctx

    // 1) Local session bearer (cookie / header / verified bridge)
    const extracted = await extractSessionBearerAsync(req, {
      sessionBridge,
      isLiveBearer: async (bearer) => !!(await sessionStore.getByBearer(bearer)),
    })
    if (extracted?.bearer) {
      const session = await sessionStore.getByBearer(extracted.bearer)
      if (session) {
        if (
          extracted.bridgeEmpNo
          && String(extracted.bridgeEmpNo) !== String(session.empNo)
        ) {
          return next()
        }
        try {
          await attachFromSession(ctx, session, { persistTouch: true })
        } catch (err) {
          // Disabled / fallback-closed sessions must not authenticate management APIs.
          if (err?.code === 'account_disabled' || err?.code === 'fallback_disabled'
            || err?.code === 'fallback_rotated' || err?.code === 'local_admin_not_configured') {
            return next()
          }
          throw err
        }
        // Keep the Desktop bridge alive as long as its session (same bearer).
        try { sessionBridge?.touch?.(extracted.bearer, ttlSeconds() * 1000) } catch { /* ignore */ }
        // Slide the browser cookie with the server idle TTL. Without this UDS_SESSION kept
        // the Max-Age from login and vanished 30 min later even for active users.
        // Throttled by slidingInterval so not every request carries Set-Cookie.
        if (slidingExpiration && extracted.via === 'cookie' && res && req
          && !res.headersSent
          && Date.now() + ttlSeconds() * 1000 - Number(session.expiresAt || 0) >= slidingIntervalMs) {
          try { appendSessionCookie(req, res, extracted.bearer) } catch { /* ignore */ }
        }
        return next()
      }
      // Explicit bearer presented but invalid — do not mix with portal cookies.
      if (extracted.via === 'header' || extracted.via === 'bridge') {
        return next()
      }
    }

    // 2) Fresh UAC login exchange from portal cookies → mint local session
    const portal = extractPortalCredentials(req)
    if (!portal) return next()

    if (!udsValidator.validateCredentials({
      empNo: portal.empNo,
      token: portal.token,
      lang: 'zh-CN',
    })) {
      return next()
    }

    const profile = await verifyEmpNoAndToken(portal.empNo, portal.token)
    if (!profile) return next()

    let role
    try {
      role = await resolveRoleOnLogin(profile.empNo)
    } catch (err) {
      ctx.authError = err?.code || err?.message
      return next()
    }

    const userContext = udsValidator.buildUserContext({
      empNo: profile.empNo,
      token: portal.token,
      lang: 'zh-CN',
      username: profile.username,
      displayName: profile.username,
      department: profile.department,
      organization: profile.organization,
      email: profile.email,
      phone: profile.phone,
    }, false)
    applyProfile(userContext, profile, { empNo: profile.empNo, token: portal.token, lang: 'zh-CN' })
    userContext.authenticatedAt = new Date().toISOString()
    userContext.sessionCreatedAt = new Date().toISOString()

    await mintSession(ctx, userContext, 'uds', { res, req })
    ctx.role = role
    ctx.permissions = rolesStore.resolvePermissions(profile.empNo, role)
    return next()
  }

  authMiddleware.udsClient = udsClient
  authMiddleware.udsValidator = udsValidator
  authMiddleware.verifyEmpNoAndToken = verifyEmpNoAndToken
  authMiddleware.mintSession = mintSession
  authMiddleware.resolveRoleOnLogin = resolveRoleOnLogin
  return authMiddleware
}

export function requirePermission(ctx, permission) {
  if (!ctx?.permissions) return false
  // Legacy alias: "super_admin" means admin-class identity (超管 / 应急 / 管理员).
  if (permission === 'super_admin') {
    return ctx.role === ROLES.SUPER_ADMIN
      || ctx.role === ROLES.FALLBACK_ADMIN
      || ctx.role === ROLES.ADMIN
  }
  return !!ctx.permissions[permission]
}
