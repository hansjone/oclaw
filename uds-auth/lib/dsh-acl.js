/**
 * Bridge UDS cookies → AsyncLocalStorage and wrap DSH session/workspace/settings.
 */
import { withUserContext, getUserContext } from './context.js'
import { computePermissions, ROLES } from './roles.js'

function parseCookie(header, name) {
  if (!header || typeof header !== 'string') return null
  for (const part of header.split(';')) {
    const idx = part.indexOf('=')
    if (idx < 0) continue
    if (part.slice(0, idx).trim() !== name) continue
    try {
      return decodeURIComponent(part.slice(idx + 1).trim())
    } catch {
      return part.slice(idx + 1).trim()
    }
  }
  return null
}

/**
 * @param {import('node:http').IncomingMessage} req
 * @param {{ sessionStore: any, rolesStore: any }} deps
 */
export async function resolveIdentityFromRequest(req, deps) {
  const cookie = req?.headers?.cookie || ''
  const empNo = parseCookie(cookie, 'PORTALSSOUser')
    || parseCookie(cookie, 'ZTEDPGSSOUser')
    || parseCookie(cookie, 'UDS_FALLBACK_USER')
  if (!empNo) return null

  const { sessionStore, rolesStore } = deps
  let userContext = null
  try {
    userContext = await sessionStore.get(empNo)
  } catch {
    userContext = null
  }
  if (!userContext) return null

  // bootstrap / resolve role
  let role = rolesStore.getRole(empNo)
  if (empNo !== 'administrator' && typeof rolesStore.bootstrapFirstUser === 'function') {
    try {
      const r = await rolesStore.bootstrapFirstUser(empNo)
      role = r.role
    } catch { /* keep getRole */ }
  }

  const permissions = computePermissions(role)
  return {
    empNo: String(empNo),
    role,
    permissions,
    userContext,
    kind: empNo === 'administrator' ? 'fallback' : 'uds',
  }
}

/**
 * Patch webServer so every route handler runs inside UDS ALS.
 * @param {any} server
 * @param {(req: any) => Promise<object|null>} resolveIdentity
 */
export function patchWebServerWithIdentity(server, resolveIdentity) {
  if (!server || server.__udsAuthPatched) return () => {}
  server.__udsAuthPatched = true

  const wrap = (handler) => {
    if (typeof handler !== 'function' || handler.__udsWrapped) return handler
    const wrapped = async (req, res, ...rest) => {
      const identity = await resolveIdentity(req)
      try {
        const pathname = new URL(req.url || '/', 'http://x').pathname
        if (
          pathname.startsWith('/dsh-ops-cron')
          && pathname !== '/dsh-ops-cron/health'
          && !identity?.empNo
        ) {
          res.writeHead(401, { 'content-type': 'application/json; charset=utf-8' })
          res.end(JSON.stringify({
            ok: false,
            error: 'login_required',
            message: '登录后才能使用定时任务',
          }))
          return
        }
      } catch { /* fall through to handler */ }
      return withUserContext(identity, () => handler(req, res, ...rest))
    }
    wrapped.__udsWrapped = true
    return wrapped
  }

  const patchTable = (table) => {
    if (!table || typeof table.entries !== 'function') return
    for (const [path, route] of table.entries()) {
      if (!route?.handler) continue
      table.set(path, { ...route, handler: wrap(route.handler) })
    }
  }

  patchTable(server.exact)
  patchTable(server.prefixes)
  if (typeof server.fallback === 'function') {
    server.fallback = wrap(server.fallback)
  }

  const origRegister = server.register.bind(server)
  server.register = (route) => origRegister({
    ...route,
    handler: wrap(route.handler),
  })

  const origFallback = server.registerFallback?.bind(server)
  if (origFallback) {
    server.registerFallback = (handler) => origFallback(wrap(handler))
  }

  const origRegisterUpgrade = server.registerUpgrade?.bind(server)
  if (origRegisterUpgrade) {
    server.registerUpgrade = (route) => origRegisterUpgrade({
      ...route,
      handler: async (req, socket, head) => {
        const identity = await resolveIdentity(req)
        return withUserContext(identity, () => route.handler(req, socket, head))
      },
    })
  }

  return () => {
    /* leave patched — reload recreates webServer fiber */
  }
}

function throwForbidden(message) {
  try {
    const { RemoteError } = require('@deepseek-ai/dsh-typert-protocol')
    throw new RemoteError('gateway/forbidden', message || 'forbidden', {})
  } catch (err) {
    if (err && (err.name === 'RemoteError' || String(err.code || '').startsWith('gateway/'))) throw err
    const e = new Error(message || 'forbidden')
    e.code = 'gateway/forbidden'
    throw e
  }
}

/**
 * Install Host ACL wrappers.
 */
export function installDshAcl(ctx, {
  sessionAcl,
  userWorkspaces,
  getWorkspaceRoot,
  rolesStore,
  ensureUserWorkspace,
}) {
  const disposers = []

  // Stamp owner on session create
  const offCreated = ctx.on('session/created', (session) => {
    try {
      const id = session?.id ?? session?.header?.id
      const identity = getUserContext()
      if (id && identity?.empNo) {
        sessionAcl.setOwner(id, identity.empNo)
      }
    } catch (err) {
      ctx.logger?.warn?.('[uds-auth] session stamp failed: %s', err.message)
    }
  })
  disposers.push(() => offCreated?.())

  ctx.inject(['sessionController'], (sctx) => {
    const sc = sctx.sessionController
    if (!sc || sc.__udsAcl) return
    sc.__udsAcl = true

    // Deeper wrap: ApiSessionList.list (cold summaries)
    if (sc.listState && typeof sc.listState.list === 'function' && !sc.listState.__udsAcl) {
      sc.listState.__udsAcl = true
      const origStateList = sc.listState.list.bind(sc.listState)
      sc.listState.list = async (signal) => {
        const items = await origStateList(signal)
        const identity = getUserContext()
        if (!identity?.empNo) return []
        if (identity.permissions?.canViewAllSessions) return items
        return (items || []).filter((row) => {
          const id = row?.sessionId ?? row?.id
          return id != null && sessionAcl.canViewSession(id)
        })
      }
      if (typeof sc.listState.search === 'function') {
        const origStateSearch = sc.listState.search.bind(sc.listState)
        sc.listState.search = async (query, signal) => {
          const value = await origStateSearch(query, signal)
          const identity = getUserContext()
          if (!identity?.empNo) return { items: [], hasMore: false }
          if (identity.permissions?.canViewAllSessions) return value
          return sessionAcl.filterListValue(value)
        }
      }
    }

    const origList = sc.list.bind(sc)
    sc.list = async (request, signal) => {
      const value = await origList(request, signal)
      const identity = getUserContext()
      if (!identity?.empNo) return { items: [] }
      if (identity.permissions?.canViewAllSessions) return value
      return sessionAcl.filterListValue(value)
    }

    const origSearch = sc.search.bind(sc)
    sc.search = async (request, signal) => {
      const value = await origSearch(request, signal)
      const identity = getUserContext()
      if (!identity?.empNo) return { items: [], hasMore: false }
      if (identity.permissions?.canViewAllSessions) return value
      return sessionAcl.filterListValue(value)
    }

    const origCreate = sc.create.bind(sc)
    sc.create = async (request) => {
      const identity = getUserContext()
      if (!identity?.empNo) throwForbidden('登录后才能创建会话')

      let req = request || {}
      if (req.workspaceId === undefined && req.cwd === undefined) {
        const ensured = await ensureUserWorkspace(identity.empNo)
        if (ensured?.workspaceId) {
          req = { ...req, workspaceId: ensured.workspaceId }
        } else if (ensured?.path) {
          req = { ...req, cwd: ensured.path }
        }
      }

      const result = await origCreate(req)
      const sid = result?.sessionId ?? result?.id
      if (sid) sessionAcl.setOwner(sid, identity.empNo)
      return result
    }
    const assertCanView = (sessionId) => {
      const identity = getUserContext()
      if (!identity?.empNo) throwForbidden('登录后才能访问会话')
      if (identity.permissions?.canViewAllSessions) return
      if (!sessionAcl.canViewSession(sessionId)) throwForbidden('无权访问该会话')
    }

    if (typeof sc.page === 'function') {
      const origPage = sc.page.bind(sc)
      sc.page = async (request, signal) => {
        assertCanView(request?.sessionId ?? request?.id)
        return origPage(request, signal)
      }
    }

    if (typeof sc.follow === 'function') {
      const origFollow = sc.follow.bind(sc)
      sc.follow = (request, signal) => {
        assertCanView(request?.sessionId ?? request?.id)
        return origFollow(request, signal)
      }
    }

    if (typeof sc.fork === 'function') {
      const origFork = sc.fork.bind(sc)
      sc.fork = async (request, signal) => {
        assertCanView(request?.sessionId ?? request?.id)
        const result = await origFork(request, signal)
        const identity = getUserContext()
        const sid = result?.sessionId ?? result?.id
        if (sid && identity?.empNo) sessionAcl.setOwner(sid, identity.empNo)
        return result
      }
    }

    if (typeof sc.rename === 'function') {
      const origRename = sc.rename.bind(sc)
      sc.rename = async (request, signal) => {
        assertCanView(request?.sessionId ?? request?.id)
        return origRename(request, signal)
      }
    }

  })

  ctx.inject(['workspaceController'], (wctx) => {
    const wc = wctx.workspaceController
    if (!wc || wc.__udsAcl) return
    wc.__udsAcl = true

    const origCreate = wc.create.bind(wc)
    wc.create = async (request) => {
      const identity = getUserContext()
      if (identity?._internalProvision) return origCreate(request)
      if (!identity?.permissions?.canCreateWorkspace) {
        throwForbidden('只有超级管理员可以创建工作区')
      }
      return origCreate(request)
    }

    // IMPORTANT: capture identity at follow() entry. Long-lived follow resumes
    // after awaits on registry watchers where AsyncLocalStorage is often empty;
    // re-reading getUserContext() per frame would treat a logged-in super_admin
    // as anonymous and filter away every pre-plugin workspace (sessions fall into
    // the ungrouped bucket).
    const allowWorkspace = (identity, ws) => {
      if (!identity?.empNo) return false
      if (identity.permissions?.canViewAllSessions) return true // super sees ALL workspaces
      const root = getWorkspaceRoot()
      return userWorkspaces.isUserPath(identity.empNo, ws?.path, root)
        || (userWorkspaces.get(identity.empNo)?.workspaceId
          && String(userWorkspaces.get(identity.empNo).workspaceId) === String(ws?.workspaceId))
    }

    const filterBaseline = (identity, baseline) => {
      if (!baseline?.items) return baseline
      return {
        ...baseline,
        items: baseline.items.filter((ws) => allowWorkspace(identity, ws)),
      }
    }

    const filterFrame = (identity, frame) => {
      if (!frame) return frame
      if (frame.type === 'baseline') {
        return { ...frame, value: filterBaseline(identity, frame.value) }
      }
      if (frame.type === 'upsert') {
        return allowWorkspace(identity, frame.workspace) ? frame : null
      }
      if (frame.type === 'order') {
        if (identity?.permissions?.canViewAllSessions) return frame
        const allowed = new Set()
        const mapped = userWorkspaces.get(identity?.empNo)?.workspaceId
        if (mapped != null) allowed.add(String(mapped))
        return {
          ...frame,
          workspaceIds: (frame.workspaceIds || []).filter((id) => allowed.has(String(id))),
        }
      }
      return frame
    }

    const origFollow = wc.follow.bind(wc)
    wc.follow = async function* (signal) {
      const identity = getUserContext()
      // Super / fallback: passthrough — never drop historical workspaces.
      if (identity?.permissions?.canViewAllSessions) {
        yield* origFollow(signal)
        return
      }
      for await (const frame of origFollow(signal)) {
        const next = filterFrame(identity, frame)
        if (next) yield next
      }
    }
  })

  // settings mutate gate
  ctx.inject(['settings'], (sctx) => {
    const settings = sctx.settings
    if (!settings || settings.__udsAcl) return
    settings.__udsAcl = true
    for (const method of ['mutate', 'update', 'replace', 'write']) {
      if (typeof settings[method] !== 'function') continue
      const orig = settings[method].bind(settings)
      settings[method] = async (...args) => {
        const identity = getUserContext()
        // Allow uds-auth namespace writes from our own settings section for admins;
        // users cannot touch any settings.
        if (!identity?.permissions?.canAccessSettings) {
          throwForbidden('当前账号无设置权限')
        }
        return orig(...args)
      }
    }
  })

    // directory picker: only super_admin may pick/create dirs (others get auto workspaces)
  ctx.inject(['directoryPicker'], (dctx) => {
    const dp = dctx.directoryPicker
    if (!dp || dp.__udsAcl) return
    dp.__udsAcl = true

    const assertCanCreateWorkspace = () => {
      const identity = getUserContext()
      if (!identity?.empNo) throwForbidden('登录后才能使用工作区')
      if (!identity?.permissions?.canCreateWorkspace) {
        throwForbidden('只有超级管理员可以创建工作区')
      }
    }

    if (typeof dp.pick === 'function') {
      const origPick = dp.pick.bind(dp)
      dp.pick = async (...args) => {
        assertCanCreateWorkspace()
        return origPick(...args)
      }
    }
    if (typeof dp.list === 'function') {
      const origList = dp.list.bind(dp)
      dp.list = async (...args) => {
        assertCanCreateWorkspace()
        return origList(...args)
      }
    }
    if (typeof dp.createDirectory === 'function') {
      const origCreate = dp.createDirectory.bind(dp)
      dp.createDirectory = async (...args) => {
        assertCanCreateWorkspace()
        return origCreate(...args)
      }
    }
  })

  return () => {
    for (const d of disposers) {
      try { d() } catch { /* ignore */ }
    }
  }
}
