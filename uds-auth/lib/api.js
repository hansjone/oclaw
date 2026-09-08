import { ROLES, ROLE_LABELS } from './roles.js'
import { requirePermission } from './middleware/auth-middleware.js'

/**
 * API handlers — 带权限守卫
 * 
 * 权限:
 *   GET  /me              → 所有人（需登录）
 *   POST /logout           → 所有人（需登录）
 *   GET  /users            → super_admin only（列出所有用户）
 *   POST /users/role       → super_admin only（修改角色）
 *   POST /users            → super_admin only（添加用户）
 *   DELETE /users/:empNo   → super_admin only（删除用户）
 *   POST /fallback/password → super_admin only（设置兜底密码）
 *   POST /fallback/clear   → super_admin only（清除兜底密码）
 */
/**
 * @param {object} config
 * @param {import('./session/store.js').SessionStore} sessionStore
 * @param {*} rolesStore
 * @param {{ skillCredentials?: { delete: (empNo: string) => void }, retainSkillCredentialsOnLogout?: () => boolean }} [extra]
 */
export function createApiHandlers(config, sessionStore, rolesStore, extra = {}) {
  async function sendRes(res, code, data) {
    res.statusCode = code >= 200 && code < 300 ? 200 : code
    res.setHeader('Content-Type', 'application/json; charset=utf-8')
    res.end(JSON.stringify(data))
  }

  async function logout(ctx) {
    const empNo = ctx.empNo
    if (empNo) await sessionStore.delete(empNo)
    // Skill 凭证轨：默认保留；retainSkillCredentialsOnLogout=false 时清除
    const retain = extra.retainSkillCredentialsOnLogout
      ? extra.retainSkillCredentialsOnLogout() !== false
      : true
    if (empNo && !retain) {
      try { extra.skillCredentials?.delete(empNo) } catch { /* ignore */ }
    }
    // Cookie clear attrs must match login (Secure + HttpOnly), or browsers keep the old cookie.
    const clear = []
    for (const name of [
      'UDS_FALLBACK_USER',
      'UDS_FALLBACK_UI',
      'PORTALSSOUser',
      'PORTALSSOCookie',
      'ZTEDPGSSOUser',
      'ZTEDPGSSOCookie',
    ]) {
      const httpOnly = name === 'UDS_FALLBACK_USER'
      const base = httpOnly
        ? (name + '=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax')
        : (name + '=; Max-Age=0; Path=/; SameSite=Lax')
      clear.push(base)
      clear.push(base + '; Secure')
    }
    ctx.res.setHeader('Set-Cookie', clear)
    await sendRes(ctx.res, 200, { message: 'Logged out' })
  }

  async function getCurrentUser(ctx) {
    const ws = ctx.provisionedWorkspace || null
    await sendRes(ctx.res, 200, {
      data: ctx.userContext ? {
        ...ctx.userContext,
        empNo: ctx.empNo,
        role: ctx.role,
        permissions: ctx.permissions,
        workspaceId: ws?.workspaceId || null,
        workspacePath: ws?.path || null,
      } : null,
      authenticated: !!ctx.userContext,
    })
  }

  // === 用户管理 (super_admin only) ===

  async function listUsers(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return sendRes(ctx.res, 403, { error: '只有超级管理员可以查看用户列表' })
    }
    const url = new URL(ctx.req.url, 'http://localhost')
    const page = url.searchParams.get('page')
    const pageSize = url.searchParams.get('pageSize')
    const q = url.searchParams.get('q') || ''
    const result = rolesStore.listPage({ page, pageSize, q })
    await sendRes(ctx.res, 200, result)
  }

  async function setUserRole(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return sendRes(ctx.res, 403, { error: '只有超级管理员可以修改角色' })
    }
    const body = await readBody(ctx.req)
    const { empNo, role } = body || {}
    if (!empNo || !role || !Object.values(ROLES).includes(role)) {
      return sendRes(ctx.res, 400, { error: '参数错误: empNo 和 role 必填' })
    }
    try {
      await rolesStore.setRole(empNo, role, ctx.role)
      await sendRes(ctx.res, 200, { message: `${empNo} 角色已更新为 ${ROLE_LABELS[role]}` })
    } catch (err) {
      await sendRes(ctx.res, 400, { error: err.message })
    }
  }

  async function addUser(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return sendRes(ctx.res, 403, { error: '只有超级管理员可以添加用户' })
    }
    const body = await readBody(ctx.req)
    const { empNo, role } = body || {}
    if (!empNo) {
      return sendRes(ctx.res, 400, { error: 'empNo 必填' })
    }
    const targetRole = role && Object.values(ROLES).includes(role) ? role : ROLES.USER
    try {
      await rolesStore.ensureUser(empNo, ctx.role)
      if (role) await rolesStore.setRole(empNo, role, ctx.role)
      await sendRes(ctx.res, 200, { message: `${empNo} 已添加为 ${ROLE_LABELS[targetRole]}` })
    } catch (err) {
      await sendRes(ctx.res, 400, { error: err.message })
    }
  }

  async function removeUser(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return sendRes(ctx.res, 403, { error: '只有超级管理员可以删除用户' })
    }
    const body = await readBody(ctx.req)
    const { empNo } = body || {}
    if (!empNo) {
      return sendRes(ctx.res, 400, { error: 'empNo 必填' })
    }
    try {
      await rolesStore.removeUser(empNo, ctx.role)
      await sessionStore.delete(empNo)
      try { extra.skillCredentials?.delete(empNo) } catch { /* ignore */ }
      await sendRes(ctx.res, 200, { message: `${empNo} 已删除` })
    } catch (err) {
      await sendRes(ctx.res, 400, { error: err.message })
    }
  }

  // === Fallback Admin (super_admin only) ===

  async function setFallbackPassword(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return sendRes(ctx.res, 403, { error: '只有超级管理员可以设置兜底密码' })
    }
    const body = await readBody(ctx.req)
    const { password } = body || {}
    try {
      await rolesStore.setFallbackPassword(password, ctx.role)
      await sendRes(ctx.res, 200, { message: '兜底管理员密码已设置' })
    } catch (err) {
      await sendRes(ctx.res, 400, { error: err.message })
    }
  }

  async function clearFallbackPassword(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return sendRes(ctx.res, 403, { error: '只有超级管理员可以清除兜底密码' })
    }
    await rolesStore.clearFallbackPassword(ctx.role)
    await sendRes(ctx.res, 200, { message: '兜底管理员密码已清除' })
  }

  async function fallbackStatus(ctx) {
    await sendRes(ctx.res, 200, {
      enabled: rolesStore.isFallbackEnabled(),
    })
  }

  return {
    logout,
    getCurrentUser,
    listUsers,
    setUserRole,
    addUser,
    removeUser,
    setFallbackPassword,
    clearFallbackPassword,
    fallbackStatus,
  }
}

async function readBody(req) {
  let body = ''
  for await (const chunk of req) body += chunk
  try { return JSON.parse(body) } catch { return null }
}
