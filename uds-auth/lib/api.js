import { ROLES, ROLE_LABELS } from './roles.js'
import { requirePermission } from './middleware/auth-middleware.js'
import { apiError, apiOk, resolveLocale, roleLabel } from './i18n.js'

/**
 * API handlers — permission guards + localized messages via stable error codes.
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

  function locale(ctx) {
    return resolveLocale(ctx.req, ctx.userContext)
  }

  function fail(ctx, code, status, vars) {
    return sendRes(ctx.res, status, apiError(code, locale(ctx), vars))
  }

  function ok(ctx, code, vars, extraFields = {}) {
    return sendRes(ctx.res, 200, { ...apiOk(code, locale(ctx), vars), ...extraFields })
  }

  function mapThrown(ctx, err, status = 400) {
    const code = err?.code || err?.message
    if (code && typeof code === 'string' && !code.includes(' ') && !/[\u4e00-\u9fff]/.test(code)) {
      return fail(ctx, code, status)
    }
    return sendRes(ctx.res, status, {
      error: 'request_failed',
      message: err?.message || String(err),
    })
  }

  async function logout(ctx) {
    const empNo = ctx.empNo
    if (empNo) await sessionStore.delete(empNo)
    const retain = extra.retainSkillCredentialsOnLogout
      ? extra.retainSkillCredentialsOnLogout() !== false
      : true
    if (empNo && !retain) {
      try { extra.skillCredentials?.delete(empNo) } catch { /* ignore */ }
    }
    const clear = []
    for (const name of [
      'UDS_FALLBACK_USER',
      'UDS_FALLBACK_UI',
      'UDS_LOCAL_ADMIN',
      'PORTALSSOUser',
      'PORTALSSOCookie',
      'ZTEDPGSSOUser',
      'ZTEDPGSSOCookie',
    ]) {
      const httpOnly = name === 'UDS_FALLBACK_USER' || name === 'UDS_LOCAL_ADMIN'
      const base = httpOnly
        ? (name + '=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax')
        : (name + '=; Max-Age=0; Path=/; SameSite=Lax')
      clear.push(base)
      clear.push(base + '; Secure')
    }
    ctx.res.setHeader('Set-Cookie', clear)
    await ok(ctx, 'logged_out')
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

  async function listUsers(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_list_users', 403)
    }
    const url = new URL(ctx.req.url, 'http://localhost')
    const page = url.searchParams.get('page')
    const pageSize = url.searchParams.get('pageSize')
    const q = url.searchParams.get('q') || ''
    const result = rolesStore.listPage({ page, pageSize, q })
    const loc = locale(ctx)
    if (Array.isArray(result.users)) {
      result.users = result.users.map((u) => ({
        ...u,
        roleLabel: roleLabel(u.role, loc) || ROLE_LABELS[u.role] || u.role,
      }))
    }
    await sendRes(ctx.res, 200, result)
  }

  async function setUserRole(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_set_role', 403)
    }
    const body = await readBody(ctx.req)
    const { empNo, role } = body || {}
    if (!empNo || !role || !Object.values(ROLES).includes(role)) {
      return fail(ctx, 'invalid_role_params', 400)
    }
    try {
      await rolesStore.setRole(empNo, role, ctx.role)
      await ok(ctx, 'role_updated', { empNo, role: roleLabel(role, locale(ctx)) })
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  async function addUser(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_add_user', 403)
    }
    const body = await readBody(ctx.req)
    const { empNo, role } = body || {}
    if (!empNo) {
      return fail(ctx, 'emp_no_required', 400)
    }
    const targetRole = role && Object.values(ROLES).includes(role) ? role : ROLES.USER
    try {
      await rolesStore.ensureUser(empNo, ctx.role)
      if (role) await rolesStore.setRole(empNo, role, ctx.role)
      await ok(ctx, 'user_added', { empNo, role: roleLabel(targetRole, locale(ctx)) })
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  async function removeUser(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_remove_user', 403)
    }
    const body = await readBody(ctx.req)
    const { empNo } = body || {}
    if (!empNo) {
      return fail(ctx, 'emp_no_required', 400)
    }
    try {
      await rolesStore.removeUser(empNo, ctx.role)
      await sessionStore.delete(empNo)
      try { extra.skillCredentials?.delete(empNo) } catch { /* ignore */ }
      await ok(ctx, 'user_removed', { empNo })
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  async function setFallbackPassword(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_set_fallback', 403)
    }
    const body = await readBody(ctx.req)
    const { password } = body || {}
    try {
      await rolesStore.setFallbackPassword(password, ctx.role)
      await ok(ctx, 'fallback_password_set')
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  async function clearFallbackPassword(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_clear_fallback', 403)
    }
    await rolesStore.clearFallbackPassword(ctx.role)
    await ok(ctx, 'fallback_password_cleared')
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
