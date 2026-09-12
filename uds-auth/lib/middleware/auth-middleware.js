import { UdsClient } from '../uds/client.js'
import { UdsValidator } from '../uds/validator.js'
import { ROLES, computePermissions } from '../roles.js'
import { searchUserByEmpNoToken } from '../uds/user-search.js'

/**
 * auth-middleware
 *
 * 正常登录：Cookie 中必须同时有 empNo + token，并用 userSearchUrl
 * （带 X-Emp-No / X-Auth-Value）直连内网拉用户详情；成功才建会话。
 * 出站请求绕过 HTTP(S)_PROXY。
 *
 * 兜底登录：仅认可已由 /api/fallback/login 或 /api/local-admin/unlock 写好的
 * administrator 会话；重启后若仅有 UDS_FALLBACK_USER cookie，会重建内存会话。
 *
 * 可选 onSkillCredentials(empNo, token)：UI 会话写入成功后并行写入 skill 凭证缓存。
 */
export function createAuthMiddleware(config, sessionStore, rolesStore, hooks = {}) {
  const onSkillCredentials = typeof hooks.onSkillCredentials === 'function'
    ? hooks.onSkillCredentials
    : null
  const udsClient = new UdsClient(config.udsAuth)
  const validatorConfig = {
    ...config.udsAuth,
    authMode: config.udsAuth?.authMode || 'token+profile',
  }
  const udsValidator = new UdsValidator(validatorConfig)
  const { cookieMaxAge, slidingExpiration } = config.session
  const userSearchUrl = config.userSearchUrl || config.udsAuth?.userSearchUrl
  const uacBaseUrl = config.udsAuth?.baseUrl || ''

  function extractEmpNo(cookieHeader) {
    const udsMatch = cookieHeader?.match(/(?:PORTALSSOUser|ZTEDPGSSOUser)=([^;]+)/)
    if (udsMatch) return { empNo: decodeURIComponent(udsMatch[1].trim()), kind: 'uds' }
    const fbMatch = cookieHeader?.match(/UDS_FALLBACK_USER=([^;]+)/)
    if (fbMatch) return { empNo: decodeURIComponent(fbMatch[1].trim()), kind: 'fallback' }
    return null
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

  async function resolveRole(empNo, kind) {
    if (kind === 'fallback' || empNo === 'administrator') {
      return rolesStore.getRole(empNo)
    }
    // 角色表空 → 首位登录者升为 super_admin；新用户默认 user；已有则返回原角色
    // 注意：getRole() 对未知用户也会返回 'user'，绝不能用 !role 判断是否已 bootstrap
    const { role, bootstrapped } = await rolesStore.bootstrapFirstUser(empNo)
    if (bootstrapped) {
      console.info('[uds-auth] BOOTSTRAP: ' + empNo + ' is now super_admin')
    }
    return role
  }

  async function verifyEmpNoAndToken(empNo, token) {
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
      return null
    }
    return out.profile
  }

  function needsProfileUpgrade(userContext) {
    if (!userContext) return true
    if (userContext.authMode === 'trust') return true
    if (userContext.authMode !== 'token+profile') return true
    const name = userContext.displayName || userContext.username || ''
    if (!name || name === userContext.empNo) return true
    return false
  }

  async function attachUser(ctx, empNo, userContext, kind, { persist = false } = {}) {
    if (persist || slidingExpiration) {
      userContext.lastActiveAt = new Date().toISOString()
      await sessionStore.setex(
        empNo,
        Math.floor(cookieMaxAge / 1000),
        userContext,
      )
    }
    if (userContext.token) {
      try { onSkillCredentials?.(empNo, userContext.token) } catch { /* ignore */ }
    }
    const role = await resolveRole(empNo, kind)
    ctx.userContext = userContext
    ctx.empNo = empNo
    ctx.role = role
    ctx.permissions = computePermissions(role)
  }

  async function authMiddleware(ctx, next) {
    const { req } = ctx
    const cookieHeader = req.headers.cookie || ''
    const extracted = extractEmpNo(cookieHeader)

    if (!extracted) return next()

    let userContext = await sessionStore.get(extracted.empNo)

    // 旧 trust 会话 / 无姓名部门：强制用 token 重查用户信息
    if (userContext && extracted.kind === 'uds' && needsProfileUpgrade(userContext)) {
      const credentials = udsValidator.extractCredentials(req)
      if (credentials && credentials.empNo === extracted.empNo && udsValidator.validateCredentials(credentials)) {
        const profile = await verifyEmpNoAndToken(credentials.empNo, credentials.token)
        if (profile) {
          userContext = applyProfile(userContext, profile, credentials)
          await sessionStore.setex(
            profile.empNo,
            Math.floor(cookieMaxAge / 1000),
            userContext,
          )
          try { onSkillCredentials?.(profile.empNo, credentials.token) } catch { /* ignore */ }
        } else {
          // 查不到资料则作废 trust 会话，避免“假登录”
          await sessionStore.delete(extracted.empNo)
          userContext = null
        }
      } else if (userContext.authMode === 'trust') {
        await sessionStore.delete(extracted.empNo)
        userContext = null
      }
    }

    if (userContext) {
      await attachUser(ctx, extracted.empNo, userContext, extracted.kind)
      return next()
    }

    // Fallback cookie survives process restart; memory session does not — rebuild.
    if (extracted.kind === 'fallback') {
      const empNo = extracted.empNo || 'administrator'
      userContext = {
        empNo,
        userId: empNo,
        username: 'Fallback Administrator',
        displayName: 'Fallback Administrator',
        isAuthenticated: true,
        role: ROLES.FALLBACK_ADMIN,
        authMode: 'fallback-cookie',
        authenticatedAt: new Date().toISOString(),
        lastActiveAt: new Date().toISOString(),
        sessionCreatedAt: new Date().toISOString(),
      }
      await attachUser(ctx, empNo, userContext, 'fallback', { persist: true })
      return next()
    }

    const credentials = udsValidator.extractCredentials(req)
    if (!credentials || !udsValidator.validateCredentials(credentials)) {
      return next()
    }
    if (credentials.empNo !== extracted.empNo) {
      return next()
    }

    const profile = await verifyEmpNoAndToken(credentials.empNo, credentials.token)
    if (!profile) {
      return next()
    }

    userContext = udsValidator.buildUserContext({
      empNo: profile.empNo,
      token: credentials.token,
      lang: credentials.lang,
      username: profile.username,
      displayName: profile.username,
      department: profile.department,
      organization: profile.organization,
      email: profile.email,
      phone: profile.phone,
    }, false)
    applyProfile(userContext, profile, credentials)
    userContext.authenticatedAt = new Date().toISOString()
    userContext.sessionCreatedAt = new Date().toISOString()

    await sessionStore.setex(
      profile.empNo,
      Math.floor(cookieMaxAge / 1000),
      userContext,
    )
    try { onSkillCredentials?.(profile.empNo, credentials.token) } catch { /* ignore */ }

    const role = await resolveRole(profile.empNo, 'uds')
    ctx.userContext = userContext
    ctx.empNo = profile.empNo
    ctx.role = role
    ctx.permissions = computePermissions(role)
    return next()
  }

  authMiddleware.udsClient = udsClient
  authMiddleware.udsValidator = udsValidator
  authMiddleware.verifyEmpNoAndToken = verifyEmpNoAndToken
  return authMiddleware
}

export function requirePermission(ctx, permission) {
  if (!ctx?.permissions) return false
  if (permission === 'super_admin') {
    return ctx.role === ROLES.SUPER_ADMIN || ctx.role === ROLES.FALLBACK_ADMIN
  }
  return !!ctx.permissions[permission]
}
