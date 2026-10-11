import { ROLES, ROLE_LABELS } from './roles.js'
import { requirePermission } from './middleware/auth-middleware.js'
import { apiError, apiOk, resolveLocale, roleLabel } from './i18n.js'
import { clearBrowserIdentity } from './identity-cache.js'
import { SESSION_COOKIE, clearSessionCookie } from './session/request-auth.js'
import { extractSessionBearerAsync } from './session/request-auth.js'
import { readBodyLimited, DEFAULT_MAX_BODY } from './utils/read-body.js'
import { audit } from './utils/audit-log.js'
import { identityFromSessionRecord } from './dsh-acl.js'

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
  // Read again inside the RolesStore mutation queue, after a slow body or a
  // concurrent demotion/logout; the role captured at request admission is stale.
  const liveActorRole = ctx => () => {
    if (rolesStore.isDisabled?.(ctx.empNo)) return ROLES.USER
    const sid = ctx.sessionId || ctx.userContext?._sessionId
    if (sid && typeof sessionStore.getBySessionIdSync === 'function') {
      const row = sessionStore.getBySessionIdSync(sid)
      return identityFromSessionRecord(row, rolesStore)?.role || ROLES.USER
    }
    return rolesStore.getRole?.(ctx.empNo) || ctx.role
  }
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
    const sessionId = ctx.sessionId || ctx.userContext?._sessionId
    // Prefer revoke current device; fall back to all devices for legacy callers.
    if (sessionId && typeof sessionStore.revokeSession === 'function') {
      await sessionStore.revokeSession(sessionId)
    } else if (empNo) {
      await sessionStore.delete(empNo)
    }
    try {
      const extracted = await extractSessionBearerAsync(ctx.req, {
        sessionBridge: extra.sessionBridge,
        isLiveBearer: async (bearer) => !!(await sessionStore.getByBearer?.(bearer)),
      })
      if (extracted?.bearer) {
        extra.sessionBridge?.revokeToken?.(extracted.bearer)
        if (typeof sessionStore.revokeBearer === 'function') {
          await sessionStore.revokeBearer(extracted.bearer)
        }
      } else if (empNo) {
        extra.sessionBridge?.revokeEmpNo?.(empNo)
      }
    } catch { /* ignore */ }
    try { clearBrowserIdentity() } catch { /* ignore */ }
    const retain = extra.retainSkillCredentialsOnLogout
      ? extra.retainSkillCredentialsOnLogout() !== false
      : true
    if (empNo && !retain) {
      try { extra.skillCredentials?.delete(empNo) } catch { /* ignore */ }
    }
    // Task capabilities outlive UI logout only if Host minted them for cron;
    // revoke current-user caps when logout is full-account style (no retain path).
    if (empNo && typeof extra.revokeTaskCapabilitiesForEmpNo === 'function' && !retain) {
      try { extra.revokeTaskCapabilitiesForEmpNo(empNo) } catch { /* ignore */ }
    }
    const clear = [
      clearSessionCookie({ secure: false }),
      clearSessionCookie({ secure: true }),
    ]
    for (const name of [
      'UDS_FALLBACK_USER',
      'UDS_FALLBACK_UI',
      'UDS_LOCAL_ADMIN',
      'PORTALSSOUser',
      'PORTALSSOCookie',
      'ZTEDPGSSOUser',
      'ZTEDPGSSOCookie',
    ]) {
      const httpOnly = name === 'UDS_FALLBACK_USER' || name === 'UDS_LOCAL_ADMIN' || name === SESSION_COOKIE
      const base = httpOnly
        ? (name + '=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax')
        : (name + '=; Max-Age=0; Path=/; SameSite=Lax')
      clear.push(base)
      clear.push(base + '; Secure')
    }
    ctx.res.setHeader('Set-Cookie', clear)
    ctx.res.setHeader('Cache-Control', 'no-store')
    audit({
      action: 'logout',
      decision: 'allow',
      actor: empNo || null,
      resource: sessionId || null,
    })
    await ok(ctx, 'logged_out')
  }

  async function getCurrentUser(ctx) {
    const ws = ctx.provisionedWorkspace || null
    ctx.res.setHeader('Cache-Control', 'no-store')
    // SEC-07: field whitelist — never return upstream token / authValue
    const uc = ctx.userContext
    const safe = uc ? {
      empNo: ctx.empNo,
      userId: uc.userId || ctx.empNo,
      username: uc.username || null,
      displayName: uc.displayName || uc.username || null,
      department: uc.department || null,
      organization: uc.organization || null,
      lang: uc.lang || null,
      isAuthenticated: true,
      authMode: uc.authMode || null,
      role: ctx.role,
      permissions: ctx.permissions,
      workspaceId: ws?.workspaceId || null,
      workspacePath: ws?.path || null,
      authenticatedAt: uc.authenticatedAt || null,
      lastActiveAt: uc.lastActiveAt || null,
    } : null
    await sendRes(ctx.res, 200, {
      data: safe,
      authenticated: !!safe,
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
      await rolesStore.setRole(empNo, role, liveActorRole(ctx))
      audit({
        action: 'set_role',
        decision: 'allow',
        actor: ctx.empNo,
        target: empNo,
        meta: { role },
      })
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
      await rolesStore.ensureUser(empNo, liveActorRole(ctx))
      if (role) await rolesStore.setRole(empNo, role, liveActorRole(ctx))
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
      await rolesStore.removeUser(empNo, liveActorRole(ctx))
      await sessionStore.delete(empNo)
      try { extra.skillCredentials?.delete(empNo) } catch { /* ignore */ }
      // A06: revoke task capabilities when account is disabled/removed.
      try { extra.revokeTaskCapabilitiesForEmpNo?.(empNo) } catch { /* ignore */ }
      await ok(ctx, 'user_removed', { empNo })
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  function isPasswordModeSession(row) {
    const mode = String(row?.userData?.authMode || row?.authMode || row?.kind || '')
    if (mode.includes('local-admin') || mode === 'sealed_box' || mode === 'local_admin') {
      return false
    }
    return mode.includes('fallback') || mode === 'fallback' || row?.kind === 'fallback'
  }

  async function revokePasswordFallbackSessions() {
    // D04/F02: revoke password-mode only — keep independent sealed-box sessions/bridges.
    const empNo = 'administrator'
    try {
      if (typeof sessionStore.revokeEmpNoMatching === 'function') {
        await sessionStore.revokeEmpNoMatching(empNo, isPasswordModeSession)
      } else if (typeof sessionStore.revokeEmpNo === 'function') {
        // Stores without matching API: do not wipe sealed-box with a blanket delete.
      }
    } catch { /* ignore */ }
    try {
      extra.sessionBridge?.revokeEmpNoKinds?.(empNo, [
        'fallback', 'fallback_password', 'fallback-password', 'fallback-login',
      ])
    } catch { /* ignore */ }
  }

  async function setFallbackPassword(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_set_fallback', 403)
    }
    const body = await readBody(ctx.req)
    const { password } = body || {}
    try {
      await rolesStore.setFallbackPassword(password, liveActorRole(ctx))
      await revokePasswordFallbackSessions()
      await ok(ctx, 'fallback_password_set')
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  async function clearFallbackPassword(ctx) {
    if (!requirePermission(ctx, 'super_admin')) {
      return fail(ctx, 'forbidden_clear_fallback', 403)
    }
    try {
      await rolesStore.clearFallbackPassword(liveActorRole(ctx))
      await revokePasswordFallbackSessions()
      await ok(ctx, 'fallback_password_cleared')
    } catch (err) {
      await mapThrown(ctx, err)
    }
  }

  async function fallbackStatus(ctx) {
    await sendRes(ctx.res, 200, {
      enabled: rolesStore.isFallbackEnabled(),
    })
  }

  async function setViewAllSessions(ctx) {
    if (!requirePermission(ctx, 'canToggleViewAllSessions')) {
      return fail(ctx, 'forbidden_view_all_sessions', 403)
    }
    const body = await readBody(ctx.req)
    const enabled = !!(body && body.enabled)
    try {
      await rolesStore.setViewAllSessionsDurable(ctx.empNo, enabled)
      ctx.permissions = rolesStore.resolvePermissions(ctx.empNo, ctx.role)
      await ok(ctx, enabled ? 'view_all_sessions_on' : 'view_all_sessions_off', null, {
        permissions: ctx.permissions,
        viewAllSessions: enabled,
      })
    } catch (err) {
      await mapThrown(ctx, err, 403)
    }
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
    setViewAllSessions,
  }
}

async function readBody(req) {
  try {
    const raw = await readBodyLimited(req, { maxBytes: DEFAULT_MAX_BODY })
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}
