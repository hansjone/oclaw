import { UdsClient } from '../uds/client.js'
import { UdsValidator } from '../uds/validator.js'
import { ROLES, computePermissions } from '../roles.js'

/**
 * auth-middleware: 从 PORTALSSOUser (empNo) 取用户，注入 role/permissions
 * 
 * 三条路径:
 *   1. 有 empNo + 有 session → 续期，注入
 *   2. 有 empNo + 无 session → 创建 session + bootstrap role
 *   3. 无 empNo → 未登录，交给下游
 */
export function createAuthMiddleware(config, sessionStore, rolesStore) {
  const udsClient = new UdsClient(config.udsAuth)
  const validatorConfig = {
    ...config.udsAuth,
    authMode: config.udsAuth?.authMode || 'trust',
  }
  const udsValidator = new UdsValidator(validatorConfig)
  const { cookieMaxAge, slidingExpiration, slidingInterval } = config.session

  function extractEmpNo(cookieHeader) {
    // 优先取 UDS 的 empNo，其次取 fallback administrator
    const udsMatch = cookieHeader?.match(/(?:PORTALSSOUser|ZTEDPGSSOUser)=([^;]+)/)
    if (udsMatch) return decodeURIComponent(udsMatch[1].trim())
    const fbMatch = cookieHeader?.match(/UDS_FALLBACK_USER=([^;]+)/)
    if (fbMatch) return decodeURIComponent(fbMatch[1].trim())
    return null
  }

  async function authMiddleware(ctx, next) {
    const { req } = ctx
    const cookieHeader = req.headers.cookie || ''
    const empNo = extractEmpNo(cookieHeader)

    if (!empNo) return next()

    // 1. 有 session → 续期
    let userContext = await sessionStore.get(empNo)
    if (userContext) {
      if (slidingExpiration && userContext.lastActiveAt) {
        const lastActive = new Date(userContext.lastActiveAt).getTime()
        if (Date.now() - lastActive >= slidingInterval) {
          userContext.lastActiveAt = new Date().toISOString()
          await sessionStore.setex(empNo, Math.floor(cookieMaxAge / 1000), userContext)
        }
      }
    } else {
      // 2. 无 session → 创建
      // 信任模式下，empNo 来自我们自己的 QR 登录流程设置的 cookie，
      // 即使没有完整的 header 凭据也应建立会话。
      const credentials = udsValidator.extractCredentials(req)
      if (udsValidator.authMode === 'trust') {
        // trust 模式：只要有 empNo 就建立会话；token 可选
        userContext = udsValidator.buildUserContext(
          credentials || { empNo, token: '', lang: 'zh-CN' },
          false,
        )
      } else {
        // verify 模式：必须有有效凭据
        if (!credentials || !udsValidator.validateCredentials(credentials)) {
          return next()
        }
        userContext = udsValidator.buildUserContext(credentials, false)
      }
      userContext.authenticatedAt = new Date().toISOString()
      userContext.lastActiveAt = new Date().toISOString()
      userContext.isAuthenticated = true
      await sessionStore.setex(empNo, Math.floor(cookieMaxAge / 1000), userContext)
    }

    // 注入 role + permissions
    const role = rolesStore.getRole(empNo)
    ctx.userContext = userContext
    ctx.empNo = empNo
    ctx.role = role
    ctx.permissions = computePermissions(role)
    return next()
  }

  authMiddleware.udsClient = udsClient
  authMiddleware.udsValidator = udsValidator
  return authMiddleware
}

/**
 * 权限守卫 — 拦截非 super_admin 的管理 API
 * 用法: 在路由里 call guard(req, res, ctx, 'canManageUsers') → true 表示通过
 */
export function requirePermission(ctx, permission) {
  if (!ctx?.permissions) return false
  if (permission === 'super_admin') return ctx.role === ROLES.SUPER_ADMIN || ctx.role === ROLES.FALLBACK_ADMIN
  return !!ctx.permissions[permission]
}
