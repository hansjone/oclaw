/**
 * Bridge UDS cookies → AsyncLocalStorage and wrap DSH session/workspace/settings.
 */
import { createRequire } from 'node:module'
import { withUserContext, getUserContext, runWithUserContext } from './context.js'
import { computePermissions, ROLES } from './roles.js'
import { resolveLocale, t } from './i18n.js'

const require = createRequire(import.meta.url)

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

/** @type {WeakMap<object, object|null|undefined>} */
const upgradeSocketIdentity = new WeakMap()

function loadWsModules(requireFn) {
  const found = []
  const seen = new Set()
  const push = (mod) => {
    if (!mod || !(mod.WebSocketServer || mod.Server)) return
    const WSS = mod.WebSocketServer || mod.Server
    if (seen.has(WSS)) return
    seen.add(WSS)
    found.push({ mod })
  }
  const attempts = []
  if (typeof requireFn === 'function') attempts.push(() => requireFn('ws'))
  attempts.push(() => {
    const { createRequire } = require('node:module')
    const { join } = require('node:path')
    return createRequire(join(process.cwd(), 'package.json'))('ws')
  })
  // Gateway often resolves its own copy under packages/api/gateway/node_modules/ws.
  attempts.push(() => {
    const { createRequire } = require('node:module')
    const { join } = require('node:path')
    return createRequire(join(process.cwd(), 'packages/api/gateway/package.json'))('ws')
  })
  attempts.push(() => {
    const cache = requireFn?.cache || require.cache || {}
    for (const id of Object.keys(cache)) {
      const norm = id.replace(/\\/g, '/')
      if (norm.endsWith('/node_modules/ws/index.js') || norm.endsWith('/node_modules/ws/wrapper.mjs')) {
        push(cache[id].exports)
      }
      if (norm.includes('/node_modules/ws/lib/websocket-server')) {
        const { createRequire } = require('node:module')
        const pkg = id.replace(/lib[\\/]websocket-server\.js$/i, 'package.json')
        try { push(createRequire(pkg)('.')) } catch { /* continue */ }
      }
    }
    return null
  })
  for (const tryLoad of attempts) {
    try { push(tryLoad()) } catch { /* next */ }
  }
  return found
}

function loadWsModule(requireFn) {
  return loadWsModules(requireFn)[0]?.mod || null
}

function bindWebSocketListenersToIdentity(ws, identity) {
  if (!ws || ws.__udsAuthBound) return
  ws.__udsAuthBound = true
  try { ws.__udsAuthIdentity = identity || null } catch { /* ignore */ }
  // Gateway RemoteStreamMuxConnection registers sync `message` listeners that
  // kick off async pump()/session.follow after the listener returns. als.run()
  // would exit too early and drop empNo → "登录后才能访问会话". enterWith keeps
  // the upgrade-time identity for the deferred stream work on this connection.
  const wrap = (listener) => {
    if (typeof listener !== 'function') return listener
    return function udsAuthBoundListener(...args) {
      // als.run preserves store across orphaned async pump()/session.follow started
      // inside the sync Gateway message listener (Node async_hooks).
      return runWithUserContext(identity || null, () => listener.apply(this, args))
    }
  }
  for (const method of ['on', 'once', 'addListener', 'prependListener', 'prependOnceListener']) {
    if (typeof ws[method] !== 'function') continue
    const orig = ws[method].bind(ws)
    ws[method] = (event, listener) => orig(event, wrap(listener))
  }
}

/**
 * remote.mux streams lose HTTP ALS after upgrade. Bind identity onto ws listeners.
 * Lazy-load `ws` from Host module cache / cwd — plugin folder cannot require it directly.
 */
function patchOneWebSocketServer(WebSocketServer, resolveIdentitySync) {
  if (!WebSocketServer?.prototype?.handleUpgrade) return false
  if (WebSocketServer.prototype.handleUpgrade.__udsAuthPatched) return true
  const orig = WebSocketServer.prototype.handleUpgrade
  function udsAuthHandleUpgrade(req, socket, head, cb) {
    let identity
    try {
      identity = (req && Object.prototype.hasOwnProperty.call(req, '__udsAuthIdentity'))
        ? req.__udsAuthIdentity
        : (socket ? upgradeSocketIdentity.get(socket) : undefined)
      if (identity === undefined && typeof resolveIdentitySync === 'function') {
        identity = resolveIdentitySync(req)
        try { if (req) req.__udsAuthIdentity = identity } catch { /* ignore */ }
        if (socket) upgradeSocketIdentity.set(socket, identity)
      }
    } catch {
      identity = null
    }
    const wrappedCb = typeof cb === 'function'
      ? (wsSocket) => {
        bindWebSocketListenersToIdentity(wsSocket, identity || null)
        return cb(wsSocket)
      }
      : cb
    return orig.call(this, req, socket, head, wrappedCb)
  }
  udsAuthHandleUpgrade.__udsAuthPatched = true
  WebSocketServer.prototype.handleUpgrade = udsAuthHandleUpgrade
  return true
}

function patchWebSocketServerForUdsIdentity(resolveIdentitySync) {
  const mods = loadWsModules(typeof require === 'function' ? require : null)
  if (!mods.length) return false
  let any = false
  for (const { mod } of mods) {
    const WebSocketServer = mod.WebSocketServer || mod.Server
    if (patchOneWebSocketServer(WebSocketServer, resolveIdentitySync)) any = true
  }
  return any
}

/**
 * Sync ACL identity from cookies + roles (no sessionStore). Used on WS upgrade/messages.
 */
export function resolveIdentityFromRequestSync(req, deps) {
  const cookie = req?.headers?.cookie || ''
  const empNo = parseCookie(cookie, 'PORTALSSOUser')
    || parseCookie(cookie, 'ZTEDPGSSOUser')
    || parseCookie(cookie, 'UDS_FALLBACK_USER')
    || parseCookie(cookie, 'UDS_FALLBACK_UI')
  if (!empNo) return null

  const token = parseCookie(cookie, 'PORTALSSOCookie')
    || parseCookie(cookie, 'ZTEDPGSSOCookie')
  const isFallback = empNo === 'administrator'
    || !!parseCookie(cookie, 'UDS_FALLBACK_USER')
    || !!parseCookie(cookie, 'UDS_FALLBACK_UI')

  // Bare portal empNo without token is NOT enough — otherwise logout/未登录
  // still leaks workspace names via leftover SSO cookies on the WebSocket.
  if (!isFallback && !token) return null

  const { rolesStore } = deps
  const role = rolesStore.getRole(empNo)
  return {
    empNo: String(empNo),
    role,
    permissions: computePermissions(role),
    userContext: {
      empNo: String(empNo),
      userId: String(empNo),
      isAuthenticated: true,
      authMode: isFallback ? 'fallback-cookie' : 'cookie-sync',
      token: token || undefined,
    },
    kind: isFallback ? 'fallback' : 'uds',
  }
}

export async function resolveIdentityFromRequest(req, deps) {
  const cookie = req?.headers?.cookie || ''
  const empNo = parseCookie(cookie, 'PORTALSSOUser')
    || parseCookie(cookie, 'ZTEDPGSSOUser')
    || parseCookie(cookie, 'UDS_FALLBACK_USER')
    || parseCookie(cookie, 'UDS_FALLBACK_UI')
  if (!empNo) return null

  const { sessionStore, rolesStore } = deps
  let userContext = null
  try {
    userContext = await sessionStore.get(empNo)
  } catch {
    userContext = null
  }

  const token = parseCookie(cookie, 'PORTALSSOCookie')
    || parseCookie(cookie, 'ZTEDPGSSOCookie')
  const isFallback = empNo === 'administrator'
    || !!parseCookie(cookie, 'UDS_FALLBACK_USER')
    || !!parseCookie(cookie, 'UDS_FALLBACK_UI')

  if (!userContext) {
    // Require session, token, or fallback cookie — never empNo alone.
    if (!token && !isFallback) return null
    userContext = {
      empNo: String(empNo),
      userId: String(empNo),
      isAuthenticated: true,
      authMode: token ? 'cookie-acl' : 'fallback-cookie',
      token: token || undefined,
      lastActiveAt: new Date().toISOString(),
    }
  }

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
    kind: isFallback ? 'fallback' : 'uds',
  }
}

/**
 * Patch webServer so every route handler runs inside UDS ALS.
 * @param {any} server
 * @param {(req: any) => Promise<object|null>} resolveIdentity
 * @param {(req: any) => object|null} resolveIdentitySync
 */
export function patchWebServerWithIdentity(server, resolveIdentity, resolveIdentitySync) {
  if (!server || server.__udsAuthPatched) return () => {}
  server.__udsAuthPatched = true

  const wrap = (handler) => {
    if (typeof handler !== 'function' || handler.__udsWrapped) return handler
    const wrapped = async (req, res, ...rest) => {
      const syncIdentity = typeof resolveIdentitySync === 'function'
        ? resolveIdentitySync(req)
        : null
      let identity = syncIdentity
      try {
        identity = (await resolveIdentity(req)) || syncIdentity
      } catch {
        identity = syncIdentity
      }
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
            message: t('err.login_required_cron', resolveLocale(req, identity)),
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

  const bindUpgradeIdentity = async (req, socket, head, prev) => {
    // Retry ws patch until Host has loaded the module.
    patchWebSocketServerForUdsIdentity(resolveIdentitySync)
    const syncIdentity = typeof resolveIdentitySync === 'function'
      ? resolveIdentitySync(req)
      : null
    let identity = syncIdentity
    try {
      identity = (await resolveIdentity(req)) || syncIdentity
    } catch {
      identity = syncIdentity
    }
    try { req.__udsAuthIdentity = identity } catch { /* ignore */ }
    if (socket) upgradeSocketIdentity.set(socket, identity)
    return withUserContext(identity, () => prev(req, socket, head))
  }

  patchWebSocketServerForUdsIdentity(resolveIdentitySync)

  try {
    const table = server.upgrades
    if (table && typeof table.entries === 'function') {
      for (const [path, route] of table.entries()) {
        if (!route?.handler || route.handler.__udsWrapped) continue
        const prev = route.handler
        const wrapped = async (req, socket, head) => bindUpgradeIdentity(req, socket, head, prev)
        wrapped.__udsWrapped = true
        table.set(path, { ...route, handler: wrapped })
      }
    }
  } catch { /* private field / unavailable */ }

  const origRegisterUpgrade = server.registerUpgrade?.bind(server)
  if (origRegisterUpgrade) {
    server.registerUpgrade = (route) => origRegisterUpgrade({
      ...route,
      handler: async (req, socket, head) => bindUpgradeIdentity(req, socket, head, route.handler),
    })
  }

  return () => {
    /* leave patched — reload recreates webServer fiber */
  }
}



function throwForbidden(code) {
  // Structural RemoteError so Gateway rpcFailure keeps the message instead of
  // remapping a plain Error to gateway/internal. Use gateway/bad-request (declared).
  const locale = resolveLocale(null, getUserContext())
  const raw = String(code || 'request_failed')
  const key = raw.startsWith('err.') ? raw : 'err.' + raw
  const message = t(key, locale)
  const err = new Error(message || 'forbidden')
  err.name = 'RemoteError'
  err.isDSHRemoteError = true
  err.code = 'gateway/bad-request'
  err.details = { udsError: raw.replace(/^err\./, '') }
  throw err
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
  getWorkspaceRegistry,
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

    const canSeeAll = (identity) => {
      if (!identity) return false
      if (identity.permissions?.canViewAllSessions) return true
      const role = identity.role || identity.userContext?.role
      if (role === 'fallback_admin' || role === 'super_admin') return true
      if (String(identity.empNo || identity.userContext?.empNo || '') === 'administrator') return true
      return false
    }

    const empOf = (identity) => identity?.empNo || identity?.userContext?.empNo || null

    const extractSessionId = (request) => {
      if (!request || typeof request !== 'object') return null
      return request.address?.sessionId
        ?? request.sessionId
        ?? request.id
        ?? request.childSessionId
        ?? null
    }

    const resolveRegistry = () => {
      try {
        if (typeof getWorkspaceRegistry === 'function') {
          const r = getWorkspaceRegistry()
          if (r) return r
        }
      } catch { /* ignore */ }
      try { return ctx.get('workspaceRegistry') } catch { return null }
    }

    const resolveSessionCwd = (sessionId, rowHint) => {
      if (rowHint?.cwd) return String(rowHint.cwd)
      try {
        const agents = ctx.get('agents')
        const agent = agents?.get?.(sessionId)
        const cwd = agent?.session?.header?.cwd
        if (cwd) return String(cwd)
      } catch { /* ignore */ }
      return null
    }

    const workspaceContainsSession = (ws, sessionId) => {
      const sid = String(sessionId)
      try {
        const ids = ws?.sessionIds
        if (ids && typeof ids[Symbol.iterator] === 'function') {
          for (const id of ids) {
            if (String(id) === sid) return true
          }
        }
      } catch { /* ignore */ }
      const raw = ws?.record?.sessionIds
      if (Array.isArray(raw) && raw.some((id) => String(id) === sid)) return true
      return false
    }

    const isVisibleWorkspace = (identity, ws) => {
      if (canSeeAll(identity)) return true
      const empNo = empOf(identity)
      if (!empNo || !ws) return false
      const root = getWorkspaceRoot()
      const wid = ws.id ?? ws.workspaceId
      const path = ws.path
      return userWorkspaces.isUserPath(empNo, path, root)
        || (userWorkspaces.get(empNo)?.workspaceId
          && String(userWorkspaces.get(empNo).workspaceId) === String(wid))
    }

    /** Workspace-first access: visible workspace membership or cwd under user path. */
    const canAccessSession = (sessionId, identity, rowHint) => {
      if (!identity || !empOf(identity)) return false
      if (canSeeAll(identity)) return true
      if (sessionId == null) return false
      const empNo = empOf(identity)
      const root = getWorkspaceRoot()
      const cwd = resolveSessionCwd(sessionId, rowHint)
      if (cwd && userWorkspaces.isUserPath(empNo, cwd, root)) return true

      const registry = resolveRegistry()
      if (!registry || typeof registry.list !== 'function') return false
      let workspaces = []
      try { workspaces = registry.list() || [] } catch { return false }
      for (const ws of workspaces) {
        if (!isVisibleWorkspace(identity, ws)) continue
        if (workspaceContainsSession(ws, sessionId)) return true
      }
      return false
    }

    // Browser HTTP always enters ALS via withUserContext(null|identity).
    // In-process Host callers (WhatsApp/IM, cron fire) never enter ALS → undefined.
    // Treat undefined as host-internal and skip UDS ACL (pre-auth behavior).
    const assertCanAccess = (request, rowHint) => {
      const identity = getUserContext()
      if (identity === undefined) return
      if (!empOf(identity)) throwForbidden('login_required_session')
      if (canSeeAll(identity)) return
      const sessionId = extractSessionId(request)
      if (!canAccessSession(sessionId, identity, rowHint)) {
        throwForbidden('session_forbidden')
      }
    }

    const assertCreateTargetAllowed = async (req, identity) => {
      if (canSeeAll(identity) || identity.permissions?.canCreateWorkspace) return
      const empNo = empOf(identity)
      const root = getWorkspaceRoot()
      if (req.workspaceId !== undefined) {
        const registry = resolveRegistry()
        const ws = registry?.get?.(req.workspaceId)
        if (!ws || !isVisibleWorkspace(identity, ws)) {
          throwForbidden('session_workspace_only')
        }
        return
      }
      if (req.cwd !== undefined) {
        if (!userWorkspaces.isUserPath(empNo, req.cwd, root)) {
          throwForbidden('session_workspace_only')
        }
      }
    }

    const filterItems = (items, identity) => (items || []).filter((row) => {
      const id = row?.sessionId ?? row?.id
      return id != null && canAccessSession(id, identity, row)
    })

    // Deeper wrap: ApiSessionList.list (cold summaries)
    if (sc.listState && typeof sc.listState.list === 'function' && !sc.listState.__udsAcl) {
      sc.listState.__udsAcl = true
      const origStateList = sc.listState.list.bind(sc.listState)
      sc.listState.list = async (signal) => {
        const items = await origStateList(signal)
        const identity = getUserContext()
        if (!empOf(identity)) return []
        if (canSeeAll(identity)) return items
        return filterItems(items, identity)
      }
      if (typeof sc.listState.search === 'function') {
        const origStateSearch = sc.listState.search.bind(sc.listState)
        sc.listState.search = async (query, signal) => {
          const value = await origStateSearch(query, signal)
          const identity = getUserContext()
          if (!empOf(identity)) return { items: [], hasMore: false }
          if (canSeeAll(identity)) return value
          return sessionAcl.filterListValue(value, (id, row) => canAccessSession(id, identity, row))
        }
      }
    }

    const origList = sc.list.bind(sc)
    sc.list = async (request, signal) => {
      const value = await origList(request, signal)
      const identity = getUserContext()
      if (!empOf(identity)) return { items: [] }
      if (canSeeAll(identity)) return value
      return sessionAcl.filterListValue(value, (id, row) => canAccessSession(id, identity, row))
    }

    const origSearch = sc.search.bind(sc)
    sc.search = async (request, signal) => {
      const value = await origSearch(request, signal)
      const identity = getUserContext()
      if (!empOf(identity)) return { items: [], hasMore: false }
      if (canSeeAll(identity)) return value
      return sessionAcl.filterListValue(value, (id, row) => canAccessSession(id, identity, row))
    }

    const origCreate = sc.create.bind(sc)
    sc.create = async (request) => {
      const identity = getUserContext()
      // WhatsApp / IM harness creates sessions in-process with no UDS ALS.
      if (identity === undefined) {
        return origCreate(request || {})
      }
      if (!empOf(identity)) throwForbidden('login_required_create_session')

      let req = { ...(request || {}) }
      await assertCreateTargetAllowed(req, identity)

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

    const waitForIdentity = async (ms = 800) => {
      let identity = getUserContext()
      // Host-internal: do not burn 800ms waiting for a browser cookie that will never appear.
      if (identity === undefined) return identity
      if (empOf(identity)) return identity
      const deadline = Date.now() + ms
      while (!empOf(identity) && Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 40))
        identity = getUserContext()
      }
      return identity
    }

    const wrapSessionMethod = (methodName) => {
      if (typeof sc[methodName] !== 'function') return
      const orig = sc[methodName].bind(sc)
      // follow is an async generator: assert inside so we can await identity.
      if (methodName === 'follow') {
        sc.follow = async function* (request, signal) {
          await waitForIdentity()
          assertCanAccess(request)
          yield* orig(request, signal)
        }
        return
      }
      sc[methodName] = async (request, signal) => {
        await waitForIdentity()
        assertCanAccess(request)
        return orig(request, signal)
      }
    }

    wrapSessionMethod('page')
    wrapSessionMethod('follow')
    wrapSessionMethod('prompt')
    wrapSessionMethod('rename')
    wrapSessionMethod('cancel')
    wrapSessionMethod('updateQueue')
    wrapSessionMethod('attachment')
    wrapSessionMethod('selectModel')

    if (typeof sc.openWorkspacePath === 'function') {
      const origOpenPath = sc.openWorkspacePath.bind(sc)
      sc.openWorkspacePath = async (request, signal) => {
        const identity = getUserContext()
        if (identity === undefined) return origOpenPath(request, signal)
        if (!empOf(identity)) throwForbidden('login_required_session')
        if (!canSeeAll(identity) && !identity.permissions?.canCreateWorkspace) {
          const path = request?.path
          if (!path || !userWorkspaces.isUserPath(empOf(identity), path, getWorkspaceRoot())) {
            throwForbidden('workspace_path_only')
          }
        }
        return origOpenPath(request, signal)
      }
    }

    if (typeof sc.fork === 'function') {
      const origFork = sc.fork.bind(sc)
      sc.fork = async (request, signal) => {
        assertCanAccess(request)
        const result = await origFork(request, signal)
        const identity = getUserContext()
        const sid = result?.sessionId ?? result?.id
        if (sid && empOf(identity)) sessionAcl.setOwner(sid, empOf(identity))
        return result
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
        throwForbidden('workspace_create_forbidden')
      }
      return origCreate(request)
    }

    // IMPORTANT: capture identity at follow() entry. Long-lived follow resumes
    // after awaits on registry watchers where AsyncLocalStorage is often empty;
    // re-reading getUserContext() per frame would treat a logged-in super_admin
    // as anonymous and filter away every pre-plugin workspace (sessions fall into
    // the ungrouped bucket).
    const canSeeAllWorkspaces = (identity) => {
      if (!identity) return false
      if (identity.permissions?.canViewAllSessions) return true
      const role = identity.role || identity.userContext?.role
      if (role === 'fallback_admin' || role === 'super_admin') return true
      // Fallback cookie user is always administrator
      if (String(identity.empNo || identity.userContext?.empNo || '') === 'administrator') return true
      return false
    }

    const allowWorkspace = (identity, ws) => {
      if (!identity?.empNo && !identity?.userContext?.empNo) return false
      if (canSeeAllWorkspaces(identity)) return true
      const empNo = identity.empNo || identity.userContext?.empNo
      const root = getWorkspaceRoot()
      const wid = ws?.workspaceId ?? ws?.id
      return userWorkspaces.isUserPath(empNo, ws?.path, root)
        || (userWorkspaces.get(empNo)?.workspaceId
          && String(userWorkspaces.get(empNo).workspaceId) === String(wid))
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
        if (canSeeAllWorkspaces(identity)) return frame
        const empNo = identity?.empNo || identity?.userContext?.empNo
        const allowed = new Set()
        const mapped = userWorkspaces.get(empNo)?.workspaceId
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
      let identity = getUserContext()
      if (!identity?.empNo && !identity?.userContext?.empNo) {
        const deadline = Date.now() + 800
        while (!identity?.empNo && !identity?.userContext?.empNo && Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 40))
          identity = getUserContext()
        }
      }
      // Missing ALS on long-lived follow generators is common. Emptying the
      // baseline here is what turned real partitions (harness/chatgpt) into
      // 未分组 for fallback_admin. Pass through; client hides UI when logged out.
      if (!identity?.empNo && !identity?.userContext?.empNo) {
        yield* origFollow(signal)
        return
      }
      if (canSeeAllWorkspaces(identity)) {
        yield* origFollow(signal)
        return
      }
      for await (const frame of origFollow(signal)) {
        const live = getUserContext() || identity
        if (canSeeAllWorkspaces(live)) {
          yield frame
          continue
        }
        const next = filterFrame(live, frame)
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
          throwForbidden('forbidden_settings')
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
      if (!identity?.empNo) throwForbidden('login_required_workspace')
      if (!identity?.permissions?.canCreateWorkspace) {
        throwForbidden('workspace_create_forbidden')
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
