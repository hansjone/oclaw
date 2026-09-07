import { UdsClient } from '../uds/client.js'
import { UdsValidator } from '../uds/validator.js'
import { ROLES, computePermissions } from '../roles.js'

/**
 * auth-middleware
 *
 * 正常登录：Cookie 中必须同时有 empNo + token，并用 userSearchUrl
 * （带 X-Emp-No / X-Auth-Value）拉用户详情；两者都成功才建会话。
 *
 * 兜底登录：仅认可已由 /api/fallback/login 写好的 administrator 会话；
 * 禁止仅靠伪造 UDS_FALLBACK_USER Cookie 提权。
 */
export function createAuthMiddleware(config, sessionStore, rolesStore) {
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

  /**
   * empNo + token → 调用户搜索接口；返回解析后的 profile 或 null
   */
  async function verifyEmpNoAndToken(empNo, token) {
    if (!userSearchUrl || !empNo || !token) return null
    try {
      const targetUrl = new URL(userSearchUrl)
      const body = JSON.stringify({
        employeeShortId: empNo,
        enableLabel: true,
        keyword: empNo,
      })
      const headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'Content-Length': Buffer.byteLength(body),
        [config.udsAuth?.empNoHeader || 'X-Emp-No']: empNo,
        [config.udsAuth?.authValueHeader || 'X-Auth-Value']: token,
      }
      if (uacBaseUrl) {
        headers.Origin = uacBaseUrl
        headers.Referer = uacBaseUrl.replace(/\/?$/, '/')
      }

      const isHttps = targetUrl.protocol === 'https:'
      const mod = await import(isHttps ? 'node:https' : 'node:http')
      const result = await new Promise((resolve, reject) => {
        const req = mod.request({
          hostname: targetUrl.hostname,
          port: targetUrl.port || (isHttps ? 443 : 80),
          path: targetUrl.pathname + targetUrl.search,
          method: 'POST',
          headers,
          timeout: 8000,
        }, (res) => {
          let data = ''
          res.on('data', (c) => { data += c })
          res.on('end', () => {
            try { resolve(JSON.parse(data)) } catch { resolve(null) }
          })
        })
        req.on('error', reject)
        req.on('timeout', () => { req.destroy(); reject(new Error('user-info timeout')) })
        req.write(body)
        req.end()
      })

      const code = result?.code?.code || result?.code
      if (code !== '0000' && code !== 0 && code !== '0') return null
      const list = Array.isArray(result?.bo) ? result.bo
        : Array.isArray(result?.bo?.rows) ? result.bo.rows
          : []
      if (!list.length) return null
      const emp = list[0]
      const resolvedEmpNo = String(
        emp.employeeShortId || emp.employeeNO || emp.empUIID || emp.empNo || empNo,
      ).trim()
      // 工号必须对得上（防 token 有效但查了别人）
      if (resolvedEmpNo && resolvedEmpNo !== String(empNo).trim()
        && !String(empNo).includes(resolvedEmpNo)
        && !resolvedEmpNo.includes(String(empNo).trim())) {
        // 宽松：短工号/长工号互含即通过；完全无关则拒绝
        const a = String(empNo).replace(/\D/g, '')
        const b = resolvedEmpNo.replace(/\D/g, '')
        if (!a || !b || !(a.includes(b) || b.includes(a))) return null
      }
      return {
        empNo: String(empNo).trim(),
        username: emp.name || emp.empName || emp.userName || empNo,
        department: emp.deptName || emp.deptShortName || emp.orgName || emp.department || '',
        email: emp.email || emp.mail || '',
        phone: emp.mobile || emp.phone || '',
        token,
      }
    } catch (err) {
      console.warn('[uds-auth] verifyEmpNoAndToken failed:', err.message)
      return null
    }
  }

  async function authMiddleware(ctx, next) {
    const { req } = ctx
    const cookieHeader = req.headers.cookie || ''
    const extracted = extractEmpNo(cookieHeader)

    if (!extracted) return next()

    // 1. 已有会话 → 滑动续期
    let userContext = await sessionStore.get(extracted.empNo)
    if (userContext) {
      if (slidingExpiration) {
        userContext.lastActiveAt = new Date().toISOString()
        await sessionStore.setex(
          extracted.empNo,
          Math.floor(cookieMaxAge / 1000),
          userContext,
        )
      }
      const role = rolesStore.getRole(extracted.empNo)
      ctx.userContext = userContext
      ctx.empNo = extracted.empNo
      ctx.role = role
      ctx.permissions = computePermissions(role)
      return next()
    }

    // 2. 无会话
    // 兜底 Cookie：绝不在这里建会话（必须走密码登录）
    if (extracted.kind === 'fallback') {
      return next()
    }

    // UDS：必须 empNo + token，且用户详情接口校验通过
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
      department: profile.department,
      email: profile.email,
      phone: profile.phone,
    }, false)
    userContext.username = profile.username
    userContext.displayName = profile.username
    userContext.department = profile.department
    userContext.email = profile.email
    userContext.phone = profile.phone
    userContext.authenticatedAt = new Date().toISOString()
    userContext.lastActiveAt = new Date().toISOString()
    userContext.isAuthenticated = true
    userContext.authMode = 'token+profile'

    await sessionStore.setex(
      profile.empNo,
      Math.floor(cookieMaxAge / 1000),
      userContext,
    )

    const role = rolesStore.getRole(profile.empNo)
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
