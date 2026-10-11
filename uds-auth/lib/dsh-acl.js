/**
 * Bridge UDS cookies → AsyncLocalStorage and wrap DSH session/workspace/settings.
 */
import { createRequire } from 'node:module'
import { resolve as resolvePath, sep as pathSep } from 'node:path'
import { withUserContext, getUserContext, runWithUserContext, enterUserContext } from './context.js'
import { resolveLocale, t } from './i18n.js'
import { extractSessionBearer, extractSessionBearerAsync } from './session/request-auth.js'
import { isLocalAdminBoxConfigured } from './local-admin.js'
import { installGatewayPolicy } from './gateway-policy.js'
import { createDesktopBootstrap } from './desktop-bootstrap.js'

const require = createRequire(import.meta.url)

/** Max time an /api/* request waits for the gateway ACL during Host startup. */
const ACL_READY_WAIT_MS = 15_000

/** True when path is outside per-user workspace root (channel/bot/harness cwd). */
export function isOutsideUserWorkspaceRoot(candidatePath, workspaceRoot) {
  if (!candidatePath) return true
  if (!workspaceRoot) return true
  try {
    const base = resolvePath(String(workspaceRoot))
    const cand = resolvePath(String(candidatePath))
    return cand !== base && !cand.startsWith(base + pathSep)
  } catch {
    return true
  }
}

/** @type {WeakMap<object, object|null|undefined>} */
const upgradeSocketIdentity = new WeakMap()

function empNoOfIdentity(identity) {
  return identity?.empNo || identity?.userContext?.empNo || null
}

/** Re-resolve when prior bind left null/empty (do not treat null as final). */
function resolveUpgradeIdentity(req, socket, resolveIdentitySync) {
  let identity
  try {
    if (req && Object.prototype.hasOwnProperty.call(req, '__udsAuthIdentity')) {
      identity = req.__udsAuthIdentity
    } else if (socket) {
      identity = upgradeSocketIdentity.get(socket)
    }
  } catch {
    identity = undefined
  }
  if (!empNoOfIdentity(identity) && typeof resolveIdentitySync === 'function') {
    try {
      identity = resolveIdentitySync(req)
    } catch {
      identity = identity ?? null
    }
    try { if (req) req.__udsAuthIdentity = identity } catch { /* ignore */ }
    if (socket) upgradeSocketIdentity.set(socket, identity)
  }
  return identity ?? null
}

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
  // kick off async pump()/session.follow after the listener returns.
  // enterWith keeps THIS connection's upgrade-time identity — never a global last-user.
  const wrap = (listener) => {
    if (typeof listener !== 'function') return listener
    return function udsAuthBoundListener(...args) {
      const live = empNoOfIdentity(ws.__udsAuthIdentity)
        ? ws.__udsAuthIdentity
        : (empNoOfIdentity(identity) ? identity : null)
      enterUserContext(live || null)
      return listener.apply(this, args)
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
/** A10: shared live sync resolver for WS prototype upgrade (survives reload). */
const _wsIdentityLive = { resolveIdentitySync: null }

function patchOneWebSocketServer(WebSocketServer) {
  if (!WebSocketServer?.prototype?.handleUpgrade) return false
  if (WebSocketServer.prototype.handleUpgrade.__udsAuthPatched) return true
  const orig = WebSocketServer.prototype.handleUpgrade
  function udsAuthHandleUpgrade(req, socket, head, cb) {
    let identity
    try {
      identity = resolveUpgradeIdentity(req, socket, _wsIdentityLive.resolveIdentitySync)
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
  if (typeof resolveIdentitySync === 'function') {
    _wsIdentityLive.resolveIdentitySync = resolveIdentitySync
  }
  const mods = loadWsModules(typeof require === 'function' ? require : null)
  if (!mods.length) return false
  let any = false
  for (const { mod } of mods) {
    const WebSocketServer = mod.WebSocketServer || mod.Server
    if (patchOneWebSocketServer(WebSocketServer)) any = true
  }
  return any
}

/**
 * Normalize session/identity auth mode → sealed_box | fallback | uds.
 * Sealed-box and password-fallback must stay independent (A08) — emergency
 * password off must not kill a live sealed_box principal (workspace follow).
 */
export function classifyAuthKind(input, empNoHint) {
  const empNo = String(
    empNoHint
    || input?.empNo
    || input?.userContext?.empNo
    || '',
  )
  const mode = String(
    input?.kind
    || input?.authMode
    || input?.userContext?.authMode
    || input?.userData?.authMode
    || '',
  )
  if (
    mode === 'local_admin'
    || mode === 'sealed_box'
    || mode === 'local-admin-unlock'
    || mode.includes('local-admin')
  ) {
    return 'sealed_box'
  }
  if (
    mode === 'fallback'
    || mode === 'fallback_password'
    || mode === 'fallback-password'
    || mode === 'fallback-login'
    || mode.includes('fallback')
  ) {
    return 'fallback'
  }
  // Legacy administrator sessions without an explicit mode were password-fallback.
  // Do not invent fallback when mode is an unknown non-empty string.
  if (empNo === 'administrator' && (!mode || mode === 'uds')) {
    return 'fallback'
  }
  return mode || 'uds'
}

/**
 * Build ACL identity from a verified local session record only.
 * Never constructs a principal from empNo cookies or non-empty upstream tokens alone.
 */
export function identityFromSessionRecord(session, rolesStore) {
  if (!session?.empNo) return null
  const empNo = String(session.empNo)
  if (rolesStore && typeof rolesStore.isDisabled === 'function' && rolesStore.isDisabled(empNo)) {
    return null
  }
  // A08: distinguish password-fallback vs sealed-box — do not share one enable switch.
  const kind = classifyAuthKind(session, empNo)
  const isSealedBox = kind === 'sealed_box'
  const isPasswordFallback = kind === 'fallback'
  if (isPasswordFallback
    && rolesStore && typeof rolesStore.isFallbackEnabled === 'function'
    && !rolesStore.isFallbackEnabled()) {
    return null
  }
  // F02/E11: sealed-box sessions require a live configured box (hot disable supported).
  if (isSealedBox && !isLocalAdminBoxConfigured()) {
    return null
  }
  // F02: password sessions stamped with older cred version are rejected after rotation.
  if (isPasswordFallback && rolesStore && typeof rolesStore.getFallbackCredVersion === 'function') {
    const liveVer = rolesStore.getFallbackCredVersion()
    const sessVer = session.userData?.fallbackCredVersion ?? session.fallbackCredVersion
    if (sessVer != null && Number(sessVer) !== Number(liveVer)) {
      return null
    }
  }
  const role = rolesStore.getRole(empNo)
  const userContext = {
    ...(session.userData || {}),
    empNo,
    userId: empNo,
    isAuthenticated: true,
    _sessionId: session.sessionId,
    authMode: kind === 'uds' ? (session.userData?.authMode || 'uds') : kind,
  }
  // Do not expose upstream token on ACL identity objects.
  if (userContext.token) delete userContext.token
  return {
    empNo,
    role,
    permissions: rolesStore.resolvePermissions(empNo, role),
    userContext,
    kind,
    authMode: userContext.authMode,
    sessionId: session.sessionId,
  }
}

function lookupSessionSync(req, deps) {
  const sessionStore = deps?.sessionStore
  if (!sessionStore || typeof sessionStore.getByBearerSync !== 'function') return null
  const extracted = extractSessionBearer(req, {
    sessionBridge: deps?.sessionBridge,
    isLiveBearer: (bearer) => !!sessionStore.getByBearerSync(bearer),
  })
  if (!extracted?.bearer) return null
  const session = sessionStore.getByBearerSync(extracted.bearer)
  if (!session) return null
  if (
    extracted.bridgeEmpNo
    && String(extracted.bridgeEmpNo) !== String(session.empNo)
  ) {
    return null
  }
  return session
}

export function resolveIdentityFromRequestSync(req, deps) {
  const session = lookupSessionSync(req, deps)
  if (!session) return null
  return identityFromSessionRecord(session, deps.rolesStore)
}

export async function resolveIdentityFromRequest(req, deps) {
  const { sessionStore, rolesStore } = deps
  const extracted = await extractSessionBearerAsync(req, {
    sessionBridge: deps?.sessionBridge,
    isLiveBearer: async (bearer) => !!(await sessionStore?.getByBearer?.(bearer)),
  })
  if (!extracted?.bearer) return null
  let session = null
  try {
    session = await sessionStore.getByBearer(extracted.bearer)
  } catch {
    session = null
  }
  if (!session) return null
  if (
    extracted.bridgeEmpNo
    && String(extracted.bridgeEmpNo) !== String(session.empNo)
  ) {
    return null
  }
  // Never bootstrap roles from ACL identity path.
  return identityFromSessionRecord(session, rolesStore)
}

/**
 * Patch webServer so every route handler runs inside UDS ALS.
 * @param {any} server
 * @param {(req: any) => Promise<object|null>} resolveIdentity
 * @param {(req: any) => object|null} resolveIdentitySync
 */
export function patchWebServerWithIdentity(server, resolveIdentity, resolveIdentitySync, validateRequest) {
  if (!server) return () => {}
  // R14: keep live resolver refs so reload/re-patch swaps identity store without
  // leaving the first patch's closed-over resolvers permanently attached.
  const live = server.__udsAuthIdentityLive || (server.__udsAuthIdentityLive = {
    resolveIdentity: null,
    resolveIdentitySync: null,
  })
  live.resolveIdentity = resolveIdentity
  live.resolveIdentitySync = resolveIdentitySync
  live.validateRequest = validateRequest
  if (server.__udsAuthPatched) {
    return () => {
      /* resolvers already live-updated */
    }
  }
  server.__udsAuthPatched = true

  /**
   * Desktop main reads settings/llm/credentials/account over /api/* the moment the
   * Host reports ready, which can precede our gateway ACL install. A hard 403 there
   * makes the native welcome read fail → hasApiKey=false → "add an API Key" prompt
   * even with keys stored. Hold (bounded) until the ACL is in place instead.
   */
  const validateWhenAclReady = async (req, upgrade) => {
    let checked = live.validateRequest?.(req, upgrade)
    const deadline = Date.now() + ACL_READY_WAIT_MS
    while (checked && !checked.ok && checked.reason === 'gateway_acl_not_ready' && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 50))
      checked = live.validateRequest?.(req, upgrade)
    }
    return checked
  }

  const wrap = (handler) => {
    if (typeof handler !== 'function' || handler.__udsWrapped) return handler
    const wrapped = async (req, res, ...rest) => {
      const checked = await validateWhenAclReady(req, false)
      if (checked && !checked.ok) {
        res.writeHead(403, { 'content-type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ ok: false, error: checked.reason }))
        return
      }
      const syncFn = live.resolveIdentitySync
      const asyncFn = live.resolveIdentity
      const syncIdentity = typeof syncFn === 'function' ? syncFn(req) : null
      let identity = syncIdentity
      try {
        identity = (typeof asyncFn === 'function' ? await asyncFn(req) : null) || syncIdentity
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
    const checked = await validateWhenAclReady(req, true)
    if (checked && !checked.ok) {
      socket?.end?.('HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
      return
    }
    // A10: always use live bag — never closed-over first-patch resolvers.
    const syncFn = live.resolveIdentitySync
    const asyncFn = live.resolveIdentity
    patchWebSocketServerForUdsIdentity(syncFn)
    const syncIdentity = typeof syncFn === 'function' ? syncFn(req) : null
    let identity = syncIdentity
    try {
      identity = (typeof asyncFn === 'function' ? await asyncFn(req) : null) || syncIdentity
    } catch {
      identity = syncIdentity
    }
    if (!empNoOfIdentity(identity) && typeof syncFn === 'function') {
      try { identity = syncFn(req) || identity } catch { /* keep */ }
    }
    try { req.__udsAuthIdentity = identity } catch { /* ignore */ }
    if (socket) upgradeSocketIdentity.set(socket, identity)
    return withUserContext(identity, () => prev(req, socket, head))
  }

  patchWebSocketServerForUdsIdentity(live.resolveIdentitySync)

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
 * Shared session visibility helpers (sidebar + @ mention + query reads).
 * Visibility:
 * - canViewAllSessions (admin-class preference, default on): see all
 * - else: own owner stamp OR own user-workspace path only
 *   (shared project / channel roots are not exposed when view-all is off)
 */
export function createSessionAccess({
  sessionAcl,
  userWorkspaces,
  getWorkspaceRoot,
  getWorkspaceRegistry,
  resolveLiveCwd,
  rolesStore,
}) {
  const empOf = (identity) => identity?.empNo || identity?.userContext?.empNo || null

  /** Always re-read prefs from live rolesStore — never trust frozen WS identity.permissions. */
  const canSeeAll = (identity) => {
    if (!identity) return false
    const empNo = empOf(identity)
    const store = typeof rolesStore === 'function' ? rolesStore() : rolesStore
    if (empNo && store && typeof store.resolvePermissions === 'function') {
      // Do not pass identity.role — store.getRole(empNo) is source of truth.
      return !!store.resolvePermissions(empNo).canViewAllSessions
    }
    if (identity.permissions?.canViewAllSessions) return true
    // No store (tests / misconfig): admin-class sees all by default.
    // If permissions were supplied and view-all is off, respect that.
    if (identity.permissions && Object.prototype.hasOwnProperty.call(identity.permissions, 'canViewAllSessions')) {
      return !!identity.permissions.canViewAllSessions
    }
    const role = identity.role || identity.userContext?.role
    return role === 'super_admin' || role === 'fallback_admin' || role === 'admin'
      || String(empNo) === 'administrator'
  }

  const resolveRegistry = () => {
    try {
      if (typeof getWorkspaceRegistry === 'function') {
        const r = getWorkspaceRegistry()
        if (r) return r
      }
    } catch { /* ignore */ }
    return null
  }

  const resolveSessionCwd = (sessionId, rowHint) => {
    if (rowHint?.cwd) return String(rowHint.cwd)
    if (rowHint?.header?.cwd) return String(rowHint.header.cwd)
    if (typeof resolveLiveCwd === 'function') {
      try {
        const cwd = resolveLiveCwd(sessionId)
        if (cwd) return String(cwd)
      } catch { /* ignore */ }
    }
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
    // View-all off: only the caller's provisioned user workspace — not shared
    // project folders (chatgpt/harness/…) or channel roots. Those stay under view-all.
    if (userWorkspaces.isUserPath(empNo, path, root)
      || (userWorkspaces.get(empNo)?.workspaceId
        && String(userWorkspaces.get(empNo).workspaceId) === String(wid))) {
      return true
    }
    return false
  }

  /**
   * SEC-13: authoritative owner wins. Foreign owner is never overridden by cwd.
   * Unowned legacy sessions may still match via own provisioned cwd / workspace.
   */
  const canAccessSession = (sessionId, identity, rowHint) => {
    if (!identity || !empOf(identity)) return false
    if (canSeeAll(identity)) return true
    if (sessionId == null) return false
    const empNo = empOf(identity)
    const owner = sessionAcl?.getOwner?.(sessionId) || null
    if (owner) {
      return String(owner) === String(empNo)
    }

    // No owner stamp — path / workspace membership only (legacy migration path).
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

  return {
    canSeeAll,
    empOf,
    resolveRegistry,
    resolveSessionCwd,
    isVisibleWorkspace,
    canAccessSession,
  }
}

/**
 * Install Host ACL wrappers.
 * `getRolesStore` / `rolesStore` is read live on every ACL check so plugin reload
 * and preference toggles take effect without re-wrapping Host controllers.
 */
export function installDshAcl(ctx, {
  sessionAcl,
  userWorkspaces,
  getWorkspaceRoot,
  rolesStore,
  getRolesStore,
  getSessionStore,
  ensureUserWorkspace,
  getWorkspaceRegistry,
}) {
  const disposers = []
  const resolveRolesStore = () => {
    if (typeof getRolesStore === 'function') {
      try { return getRolesStore() } catch { return null }
    }
    if (typeof rolesStore === 'function') {
      try { return rolesStore() } catch { return null }
    }
    return rolesStore || null
  }
  const resolveSessionStore = () => {
    if (typeof getSessionStore === 'function') {
      try { return getSessionStore() } catch { return null }
    }
    return null
  }

  // Shared live bag: re-install updates this even when Host controllers are already wrapped.
  const live = installDshAcl._live || (installDshAcl._live = { access: null })
  const rebuildAccess = () => {
    live.access = createSessionAccess({
      sessionAcl,
      userWorkspaces,
      getWorkspaceRoot,
      rolesStore: resolveRolesStore,
      getWorkspaceRegistry: () => {
        try {
          if (typeof getWorkspaceRegistry === 'function') {
            const r = getWorkspaceRegistry()
            if (r) return r
          }
        } catch { /* ignore */ }
        try { return ctx.get('workspaceRegistry') } catch { return null }
      },
      resolveLiveCwd: (sessionId) => {
        try {
          const agents = ctx.get('agents')
          // F06: use raw lookup — never the ACL-wrapped get (avoids recursion).
          const rawGet = agents?.__udsRawGet || agents?.get
          const agent = typeof rawGet === 'function' ? rawGet.call(agents, sessionId) : null
          return agent?.session?.header?.cwd || null
        } catch {
          return null
        }
      },
    })
  }
  rebuildAccess()

  const canSeeAll = (identity) => live.access.canSeeAll(identity)
  const empOf = (identity) => live.access.empOf(identity)
  const resolveRegistry = () => live.access.resolveRegistry()
  const isVisibleWorkspace = (identity, ws) => live.access.isVisibleWorkspace(identity, ws)
  const canAccessSession = (sessionId, identity, rowHint) => (
    live.access.canAccessSession(sessionId, identity, rowHint)
  )

  /** SEC-10: always read current role/prefs — never trust frozen identity.permissions. */
  const livePermissions = (identity) => {
    const emp = empOf(identity)
    const store = resolveRolesStore()
    if (emp && store && typeof store.resolvePermissions === 'function') {
      return store.resolvePermissions(emp)
    }
    return identity?.permissions || {}
  }

  /**
   * A01: every ACL entry must re-validate session + account + auth mode.
   * When no session store is wired (unit harness), skip the store check.
   */
  const assertPrincipalLive = (identity) => {
    if (identity === undefined) return
    if (!empOf(identity)) throwForbidden('login_required_session')
    const roles = resolveRolesStore()
    const emp = empOf(identity)
    if (roles && typeof roles.isDisabled === 'function' && roles.isDisabled(emp)) {
      throwForbidden('account_disabled')
    }
    const store = resolveSessionStore()
    let sessionRow = null
    if (store && typeof store.getBySessionIdSync === 'function') {
      const sid = identity.sessionId || identity.userContext?._sessionId
      if (!sid || !store.getBySessionIdSync(sid)) throwForbidden('session_revoked')
      sessionRow = store.getBySessionIdSync(sid)
      if (sessionRow?.empNo && String(sessionRow.empNo) !== String(emp)) throwForbidden('session_revoked')
    }
    // Prefer live session row kind — incomplete ALS identities (empNo-only) used to
    // default administrator→fallback and wipe workspace follow when emergency
    // password is unset, even though the session is sealed_box.
    const kind = classifyAuthKind(sessionRow || identity, emp)
    if (kind === 'sealed_box' && !isLocalAdminBoxConfigured()) {
      throwForbidden('local_admin_not_configured')
    }
    if (kind === 'fallback') {
      if (roles && typeof roles.isFallbackEnabled === 'function' && !roles.isFallbackEnabled()) {
        throwForbidden('fallback_disabled')
      }
      const generation = identity.userContext?.fallbackCredVersion
        ?? sessionRow?.userData?.fallbackCredVersion
      if (generation != null && roles?.getFallbackCredVersion?.() !== Number(generation)) {
        throwForbidden('fallback_rotated')
      }
    }
  }

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

  const extractSessionId = (request) => {
    if (!request || typeof request !== 'object') return null
    return request.address?.sessionId
      ?? request.sessionId
      ?? request.id
      ?? request.childSessionId
      ?? null
  }

  // Browser HTTP always enters ALS via withUserContext(null|identity).
  // In-process Host callers (WhatsApp/IM, cron fire) never enter ALS → undefined.
  // Treat undefined as host-internal and skip UDS ACL (pre-auth behavior).
  const assertCanAccess = (request, rowHint) => {
    const identity = getUserContext()
    if (identity === undefined) return
    assertPrincipalLive(identity)
    if (canSeeAll(identity)) return
    const sessionId = extractSessionId(request)
    if (!canAccessSession(sessionId, identity, rowHint)) {
      throwForbidden('session_forbidden')
    }
  }

  const assertSessionReadable = (sessionId, rowHint) => {
    const identity = getUserContext()
    if (identity === undefined) return
    assertPrincipalLive(identity)
    if (canSeeAll(identity)) return
    if (!canAccessSession(sessionId, identity, rowHint)) {
      throwForbidden('session_forbidden')
    }
  }

  ctx.inject(['typertGateway'], (gctx) => {
    const desktopBootstrap = createDesktopBootstrap({
      getService: name => { try { return gctx.get(name) } catch { return null } },
      deny: throwForbidden,
    })
    installGatewayPolicy(gctx.typertGateway, { identity: getUserContext, assertPrincipal: assertPrincipalLive,
      assertSession: assertSessionReadable, permissions: livePermissions, deny: throwForbidden, desktopBootstrap })
  })

  const filterSessionRecords = (records, identity) => (records || []).filter((row) => {
    const id = row?.header?.id ?? row?.sessionId ?? row?.id
    return id != null && canAccessSession(id, identity, {
      cwd: row?.header?.cwd ?? row?.cwd,
      header: row?.header,
    })
  })

  // @ mention discovery (SessionReferenceResolver) lists via sessionQuery.listSessions,
  // bypassing sessionController ACL — filter the corpus here.
  ctx.inject(['sessionQuery'], (qctx) => {
    const sq = qctx.sessionQuery
    if (!sq || sq.__udsAcl) return
    sq.__udsAcl = true

    if (typeof sq.listSessions === 'function') {
      const origList = sq.listSessions.bind(sq)
      sq.listSessions = async (signal) => {
        const identity = getUserContext()
        if (identity === undefined) return origList(signal)
        assertPrincipalLive(identity)
        const records = await origList(signal)
        if (!empOf(identity)) return []
        if (canSeeAll(identity)) return records
        return filterSessionRecords(records, identity)
      }
    }

    if (typeof sq.filterSessions === 'function') {
      const origFilter = sq.filterSessions.bind(sq)
      sq.filterSessions = async (filters, signal) => {
        const identity = getUserContext()
        if (identity === undefined) return origFilter(filters, signal)
        assertPrincipalLive(identity)
        const records = await origFilter(filters, signal)
        if (!empOf(identity)) return []
        if (canSeeAll(identity)) return records
        return filterSessionRecords(records, identity)
      }
    }

    if (typeof sq.searchSessions === 'function') {
      const origSearch = sq.searchSessions.bind(sq)
      sq.searchSessions = async (request, exec) => {
        const identity = getUserContext()
        if (identity === undefined) return origSearch(request, exec)
        assertPrincipalLive(identity)
        const page = await origSearch(request, exec)
        if (!empOf(identity)) {
          return page && typeof page === 'object'
            ? { ...page, hits: [], items: [] }
            : page
        }
        if (canSeeAll(identity)) return page
        if (!page || typeof page !== 'object') return page
        const filterHits = (hits) => (hits || []).filter((hit) => {
          const id = hit?.sessionId ?? hit?.header?.id ?? hit?.id
          return id != null && canAccessSession(id, identity, {
            cwd: hit?.cwd ?? hit?.header?.cwd,
            header: hit?.header,
          })
        })
        return {
          ...page,
          ...(Array.isArray(page.hits) ? { hits: filterHits(page.hits) } : {}),
          ...(Array.isArray(page.items) ? { items: filterHits(page.items) } : {}),
        }
      }
    }

    for (const method of ['readSession', 'readSurface', 'readTitle', 'readTitleSnapshot', 'listEvents', 'observeSession']) {
      if (typeof sq[method] !== 'function') continue
      const orig = sq[method].bind(sq)
      sq[method] = async (sessionId, ...rest) => {
        assertSessionReadable(sessionId)
        return orig(sessionId, ...rest)
      }
    }
  })

  // Belt-and-suspenders: filter @ candidates even if listSessions wrap order changes.
  ctx.inject(['sessionReferenceResolver'], (rctx) => {
    const resolver = rctx.sessionReferenceResolver
    if (!resolver || resolver.__udsAcl) return
    resolver.__udsAcl = true

    if (typeof resolver.listCandidates === 'function') {
      const origList = resolver.listCandidates.bind(resolver)
      resolver.listCandidates = async (agent, query, limit, signal) => {
        const identity = getUserContext()
        if (identity === undefined) return origList(agent, query, limit, signal)
        assertPrincipalLive(identity)
        const candidates = await origList(agent, query, limit, signal)
        if (!empOf(identity)) return []
        if (canSeeAll(identity)) return candidates
        return (candidates || []).filter((c) => canAccessSession(c?.sessionId, identity, {
          cwd: c?.cwd,
        }))
      }
    }

    if (typeof resolver.prepare === 'function') {
      const origPrepare = resolver.prepare.bind(resolver)
      resolver.prepare = async (agent, content, references, signal) => {
        const identity = getUserContext()
        if (identity !== undefined) {
          assertPrincipalLive(identity)
          if (!empOf(identity)) throwForbidden('login_required_session')
          if (!canSeeAll(identity)) {
            for (const ref of references || []) {
              const sid = ref?.sessionId
              if (sid != null && !canAccessSession(sid, identity)) {
                throwForbidden('session_forbidden')
              }
            }
          }
        }
        return origPrepare(agent, content, references, signal)
      }
    }
  })

  ctx.inject(['sessionController'], (sctx) => {
    const sc = sctx.sessionController
    if (!sc || sc.__udsAcl) return
    sc.__udsAcl = true

    const assertCreateTargetAllowed = async (req, identity) => {
      // R04: live permissions after demotion — never trust frozen identity.permissions.
      const perms = livePermissions(identity)
      if (canSeeAll(identity) || perms.canCreateWorkspace) return
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
        const identity = getUserContext()
        if (identity === undefined) return origStateList(signal)
        assertPrincipalLive(identity)
        const items = await origStateList(signal)
        if (!empOf(identity)) return []
        if (canSeeAll(identity)) return items
        return filterItems(items, identity)
      }
      if (typeof sc.listState.search === 'function') {
        const origStateSearch = sc.listState.search.bind(sc.listState)
        sc.listState.search = async (query, signal) => {
          const identity = getUserContext()
          if (identity === undefined) return origStateSearch(query, signal)
          assertPrincipalLive(identity)
          const value = await origStateSearch(query, signal)
          if (!empOf(identity)) return { items: [], hasMore: false }
          if (canSeeAll(identity)) return value
          return sessionAcl.filterListValue(value, (id, row) => canAccessSession(id, identity, row))
        }
      }
    }

    const origList = sc.list.bind(sc)
    sc.list = async (request, signal) => {
      const identity = getUserContext()
      if (identity === undefined) return origList(request, signal)
      assertPrincipalLive(identity)
      const value = await origList(request, signal)
      if (!empOf(identity)) return { items: [] }
      if (canSeeAll(identity)) return value
      return sessionAcl.filterListValue(value, (id, row) => canAccessSession(id, identity, row))
    }

    const origSearch = sc.search.bind(sc)
    sc.search = async (request, signal) => {
      const identity = getUserContext()
      if (identity === undefined) return origSearch(request, signal)
      assertPrincipalLive(identity)
      const value = await origSearch(request, signal)
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

      assertPrincipalLive(identity)
      let req = { ...(request || {}) }
      await assertCreateTargetAllowed(req, identity)

      // SEC-15: never fall through to Host default cwd when provisioning fails.
      if (req.workspaceId === undefined && req.cwd === undefined) {
        const ensured = await ensureUserWorkspace(identity.empNo)
        if (ensured?.workspaceId) {
          req = { ...req, workspaceId: ensured.workspaceId }
        } else if (ensured?.path) {
          req = { ...req, cwd: ensured.path }
        } else {
          throwForbidden('workspace_provision_failed')
        }
      }
      if (req.workspaceId === undefined && req.cwd === undefined) {
        throwForbidden('workspace_provision_failed')
      }
      if (req.workspaceId != null && req.cwd != null) {
        // Ambiguous dual target — keep workspaceId, drop cwd.
        const { cwd: _drop, ...rest } = req
        req = rest
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
      // Wait briefly for connection-bound ALS only — never borrow another user's identity.
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
          const identity = await waitForIdentity()
          assertCanAccess(request)
          // Long-lived generator: pin ALS so history frames keep empNo after awaits.
          if (identity !== undefined) enterUserContext(identity)
          for await (const frame of orig(request, signal)) {
            // SEC-10: re-check before each push after demote/logout.
            assertCanAccess(request)
            yield frame
          }
        }
        return
      }
      sc[methodName] = async (request, signal) => {
        const identity = await waitForIdentity()
        assertCanAccess(request)
        if (identity !== undefined) enterUserContext(identity)
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
    wrapSessionMethod('projections')

    if (typeof sc.control === 'function') {
      const originalControl = sc.control.bind(sc)
      sc.control = async function* (signal) {
        for await (const frame of originalControl(signal)) {
          const identity = getUserContext()
          if (identity === undefined) { yield frame; continue }
          assertPrincipalLive(identity)
          if (frame.type === 'baseline') {
            const projections = Object.fromEntries(Object.entries(frame.value?.projections || {})
              .filter(([id]) => canAccessSession(id, identity)))
            yield { ...frame, value: { ...frame.value, projections } }
          } else if (frame.type === 'projection' && canAccessSession(frame.sessionId, identity)) {
            yield frame
          }
        }
      }
    }

    if (typeof sc.openWorkspacePath === 'function') {
      const origOpenPath = sc.openWorkspacePath.bind(sc)
      sc.openWorkspacePath = async (request, signal) => {
        const identity = getUserContext()
        if (identity === undefined) return origOpenPath(request, signal)
        if (!empOf(identity)) throwForbidden('login_required_session')
        const perms = livePermissions(identity)
        if (!canSeeAll(identity) && !perms.canCreateWorkspace) {
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
      // undefined = trusted Host (runAsHost); null/missing = anonymous browser — deny.
      if (identity === undefined) return origCreate(request)
      assertPrincipalLive(identity)
      if (!empOf(identity)) throwForbidden('login_required_create_workspace')
      if (!livePermissions(identity).canCreateWorkspace) {
        throwForbidden('workspace_create_forbidden')
      }
      return origCreate(request)
    }

    /** SEC-11: guard workspace write / archive / pin Remote methods. */
    const projectIdList = (identity, ids) => {
      if (!Array.isArray(ids)) return ids
      if (canSeeAll(identity)) return ids
      return ids.filter((id) => id != null && canAccessSession(String(id), identity))
    }

    const projectMutationResult = (identity, value) => {
      if (value == null || typeof value !== 'object') return value
      if (canSeeAll(identity)) return value
      const next = { ...value }
      for (const key of [
        'archivedSessionIds', 'pinnedSessionIds', 'sessionIds', 'ids', 'items',
      ]) {
        if (Array.isArray(next[key])) {
          if (key === 'items') {
            next[key] = next[key].filter((row) => {
              const id = row?.sessionId ?? row?.id
              return id == null || canAccessSession(String(id), identity, row)
            })
          } else {
            next[key] = projectIdList(identity, next[key])
          }
        }
      }
      return next
    }

    const wrapWorkspaceWrite = (methodName, { sessionScoped = false } = {}) => {
      if (typeof wc[methodName] !== 'function') return
      const orig = wc[methodName].bind(wc)
      wc[methodName] = async (...args) => {
        const identity = getUserContext()
        if (identity === undefined) return orig(...args)
        assertPrincipalLive(identity)
        if (!empOf(identity)) throwForbidden('login_required_workspace')
        if (sessionScoped) {
          const sid = args[0]?.sessionId ?? args[0]?.id ?? args[0]
          if (sid != null && !canSeeAll(identity) && !canAccessSession(sid, identity)) {
            throwForbidden('session_forbidden')
          }
        } else if (!livePermissions(identity).canCreateWorkspace) {
          throwForbidden('workspace_create_forbidden')
        }
        const result = await orig(...args)
        return projectMutationResult(identity, result)
      }
    }
    wrapWorkspaceWrite('rename')
    wrapWorkspaceWrite('delete')
    wrapWorkspaceWrite('insertBefore')
    wrapWorkspaceWrite('insertSessionBefore', { sessionScoped: true })
    wrapWorkspaceWrite('archiveSession', { sessionScoped: true })
    wrapWorkspaceWrite('unarchiveSession', { sessionScoped: true })
    wrapWorkspaceWrite('pinSession', { sessionScoped: true })
    wrapWorkspaceWrite('unpinSession', { sessionScoped: true })

    const canSeeAllWorkspaces = (identity) => {
      if (!identity) return false
      return canSeeAll(identity)
    }

    const allowWorkspace = (identity, ws) => {
      if (!identity?.empNo && !identity?.userContext?.empNo) return false
      if (canSeeAllWorkspaces(identity)) return true
      const empNo = identity.empNo || identity.userContext?.empNo
      const root = getWorkspaceRoot()
      const wid = ws?.workspaceId ?? ws?.id
      if (userWorkspaces.isUserPath(empNo, ws?.path, root)
        || (userWorkspaces.get(empNo)?.workspaceId
          && String(userWorkspaces.get(empNo).workspaceId) === String(wid))) {
        return true
      }
      return false
    }

    const filterSessionIdList = (identity, ids) => {
      if (!Array.isArray(ids)) return ids
      if (canSeeAllWorkspaces(identity)) return ids
      return ids.filter((id) => id != null && canAccessSession(String(id), identity))
    }

    const projectWorkspaceItem = (identity, ws) => {
      if (!ws || typeof ws !== 'object') return ws
      if (canSeeAllWorkspaces(identity)) return ws
      if (!Array.isArray(ws.sessionIds)) return ws
      return {
        ...ws,
        sessionIds: filterSessionIdList(identity, ws.sessionIds),
      }
    }

    const filterBaseline = (identity, baseline) => {
      if (!baseline) return baseline
      const next = { ...baseline }
      if (Array.isArray(baseline.items)) {
        next.items = baseline.items
          .filter((ws) => allowWorkspace(identity, ws))
          .map((ws) => projectWorkspaceItem(identity, ws))
      }
      // SEC-12: do not leak foreign archived/pinned session ids.
      if (Array.isArray(baseline.archivedSessionIds)) {
        next.archivedSessionIds = filterSessionIdList(identity, baseline.archivedSessionIds)
      }
      if (Array.isArray(baseline.pinnedSessionIds)) {
        next.pinnedSessionIds = filterSessionIdList(identity, baseline.pinnedSessionIds)
      }
      return next
    }

    const filterFrame = (identity, frame) => {
      if (!frame) return frame
      if (frame.type === 'baseline') {
        return { ...frame, value: filterBaseline(identity, frame.value) }
      }
      if (frame.type === 'upsert') {
        if (!allowWorkspace(identity, frame.workspace)) return null
        return {
          ...frame,
          workspace: projectWorkspaceItem(identity, frame.workspace),
        }
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
      // R08: DSH remove frames carry workspaceId (not sessionId).
      if (frame.type === 'remove') {
        const wid = frame.workspaceId ?? frame.id ?? frame.value?.workspaceId
        if (wid != null) {
          const ws = { workspaceId: wid, id: wid, path: frame.path }
          return allowWorkspace(identity, ws) ? frame : null
        }
      }
      // SEC-12: archive/pin frames — drop if session not accessible.
      const sid = frame.sessionId ?? frame.id ?? frame.value?.sessionId
      if (sid != null && ['archive', 'unarchive', 'pin', 'unpin', 'archived', 'pinned'].includes(frame.type)) {
        return canAccessSession(String(sid), identity) ? frame : null
      }
      if (Array.isArray(frame.archivedSessionIds) || Array.isArray(frame.pinnedSessionIds)) {
        return {
          ...frame,
          ...(Array.isArray(frame.archivedSessionIds)
            ? { archivedSessionIds: filterSessionIdList(identity, frame.archivedSessionIds) }
            : {}),
          ...(Array.isArray(frame.pinnedSessionIds)
            ? { pinnedSessionIds: filterSessionIdList(identity, frame.pinnedSessionIds) }
            : {}),
        }
      }
      // Unknown frame types: default deny (do not pass through).
      if (!['baseline', 'upsert', 'order'].includes(frame.type)) {
        return null
      }
      return frame
    }

    const origFollow = wc.follow.bind(wc)
    const emptyWorkspaceBaseline = () => ({
      type: 'baseline',
      value: { items: [], archivedSessionIds: [], pinnedSessionIds: [] },
    })
    const holdUntilAbort = async (signal) => {
      if (!signal || signal.aborted) return
      await new Promise((resolve) => {
        signal.addEventListener('abort', () => resolve(), { once: true })
      })
    }
    wc.follow = async function* (signal) {
      // Identity is fixed at WS upgrade (ticket/bridge). Waiting on ALS cannot
      // turn an anonymous mux into an admin — Desktop must soft-reconnect.
      //
      // Critical Desktop bug: returning with ZERO frames makes
      // WorkspaceStateStream throw a non-Carrier Error
      // ("ended before its opening snapshot"), which is terminal — later
      // authenticated reconnects never repaint and the sidebar stays「未分组」
      // even though a fresh follow with a ticket returns all workspaces.
      const identity = getUserContext()
      // undefined = trusted Host (runAsHost) — full feed.
      if (identity === undefined) {
        yield* origFollow(signal)
        return
      }
      // Anonymous browser: empty snapshot + hold until reconnect aborts us.
      if (!empOf(identity)) {
        yield emptyWorkspaceBaseline()
        await holdUntilAbort(signal)
        return
      }
      // R04: never bypass projection for admin-at-subscribe — re-check every frame after demotion.
      let sentBaseline = false
      for await (const frame of origFollow(signal)) {
        const liveId = getUserContext() || identity
        try {
          assertPrincipalLive(liveId)
        } catch {
          if (!sentBaseline) yield emptyWorkspaceBaseline()
          return
        }
        if (frame?.type === 'baseline') sentBaseline = true
        if (canSeeAllWorkspaces(liveId)) {
          yield frame
          continue
        }
        const next = filterFrame(liveId, frame)
        if (next) {
          if (next.type === 'baseline') sentBaseline = true
          yield next
        }
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
        if (identity === undefined) return orig(...args)
        assertPrincipalLive(identity)
        if (!empOf(identity) || !livePermissions(identity).canAccessSettings) {
          throwForbidden('forbidden_settings')
        }
        return orig(...args)
      }
    }
  })

  // credentialsController — deny browser users from reading/writing Host credentials
  ctx.inject(['credentialsController'], (cctx) => {
    const cc = cctx.credentialsController
    if (!cc || cc.__udsAcl) return
    cc.__udsAcl = true
    const guard = (methodName) => {
      if (typeof cc[methodName] !== 'function') return
      const orig = cc[methodName].bind(cc)
      cc[methodName] = async (...args) => {
        const identity = getUserContext()
        if (identity === undefined) return orig(...args)
        assertPrincipalLive(identity)
        if (!empOf(identity) || !livePermissions(identity).canAccessSettings) {
          throwForbidden('forbidden_settings')
        }
        return orig(...args)
      }
    }
    for (const m of ['get', 'set', 'list', 'delete', 'update', 'read', 'write']) {
      guard(m)
    }
  })

  // R02: jobController — request.sessionId is a resource id, not caller identity.
  ctx.inject(['jobController'], (jctx) => {
    const jc = jctx.jobController
    if (!jc || jc.__udsAcl) return
    jc.__udsAcl = true
    for (const method of ['kill', 'list', 'follow']) {
      if (typeof jc[method] !== 'function') continue
      const orig = jc[method].bind(jc)
      if (method === 'follow' || method === 'list') {
        jc[method] = async function* (request, signal) {
          assertCanAccess(request)
          for await (const frame of orig(request, signal)) {
            try { assertCanAccess(request) } catch { return }
            yield frame
          }
        }
      } else {
        jc[method] = async (request, signal) => {
          assertCanAccess(request)
          return orig(request, signal)
        }
      }
    }
  })

  // A03: terminalController — preserve AsyncIterable for streams; wrap retain.
  ctx.inject(['terminalController'], (tctx) => {
    const tc = tctx.terminalController
    if (!tc || tc.__udsAcl) return
    tc.__udsAcl = true

    const terminalSessionId = (agentOrReq, rest) => (
      agentOrReq?.session?.header?.id
      ?? agentOrReq?.sessionId
      ?? agentOrReq?.id
      ?? (typeof agentOrReq === 'string' ? agentOrReq : null)
      ?? rest?.[0]?.sessionId
      ?? null
    )

    const assertTerminalAccess = (agentOrReq, rest = []) => {
      const sid = terminalSessionId(agentOrReq, rest)
      if (sid != null) assertSessionReadable(sid)
      else {
        const identity = getUserContext()
        if (identity !== undefined) assertPrincipalLive(identity)
      }
    }

    if (typeof tc.list === 'function') {
      const origList = tc.list.bind(tc)
      tc.list = (sessionId, ...rest) => {
        assertSessionReadable(sessionId)
        return origList(sessionId, ...rest)
      }
    }

    // Stream methods must return AsyncIterable synchronously (Gateway does not await).
    for (const method of ['follow', 'retain']) {
      if (typeof tc[method] !== 'function') continue
      const orig = tc[method].bind(tc)
      tc[method] = function udsAuthTerminalStream(agentOrReq, ...rest) {
        try {
          assertTerminalAccess(agentOrReq, rest)
        } catch {
          // Deny as empty stream so callers iterating frames get no data (V11).
          return (async function* () {})()
        }
        const out = orig(agentOrReq, ...rest)
        // If Host returns a thenable accidentally, still expose async iteration.
        const iterate = async function* () {
          const stream = typeof out?.then === 'function' ? await out : out
          for await (const frame of stream) {
            try { assertTerminalAccess(agentOrReq, rest) } catch { return }
            yield frame
          }
        }
        if (out && typeof out[Symbol.asyncIterator] === 'function' && typeof out.then !== 'function') {
          return (async function* () {
            for await (const frame of out) {
              try { assertTerminalAccess(agentOrReq, rest) } catch { return }
              yield frame
            }
          })()
        }
        return iterate()
      }
    }

    for (const method of ['create', 'resize', 'write', 'close', 'rename', 'dispose']) {
      if (typeof tc[method] !== 'function') continue
      const orig = tc[method].bind(tc)
      tc[method] = async (agentOrReq, ...rest) => {
        assertTerminalAccess(agentOrReq, rest)
        return orig(agentOrReq, ...rest)
      }
    }
  })

  // R02: agents.get — Typert / Agent lookup by sessionId under UDS ACL.
  ctx.inject(['agents'], (actx) => {
    const agents = actx.agents
    if (!agents || agents.__udsAcl) return
    agents.__udsAcl = true
    if (typeof agents.get === 'function') {
      const origGet = agents.get.bind(agents)
      // F06: preserve unbound raw get for resolveLiveCwd (no ACL recursion).
      agents.__udsRawGet = origGet
      agents.get = (sessionId, ...rest) => {
        const identity = getUserContext()
        if (identity !== undefined) assertSessionReadable(sessionId)
        return origGet(sessionId, ...rest)
      }
    }
  })

  // A02: authorize on real target path/key after resolve — not only displayPath.
  // Soft-deny for /api/file: Host serveFile only maps FsError→403; RemoteError escapes.
  ctx.inject(['fs'], (fctx) => {
    const fs = fctx.fs
    if (!fs || fs.__udsAcl) return
    fs.__udsAcl = true
    const pathFromTarget = (target) => {
      if (typeof target === 'string') return target
      if (!target || typeof target !== 'object') return null
      // Prefer realpath / targetKey over displayPath (junction-safe).
      return target.targetKey || target.realpath || target.realPath
        || target.path || target.displayPath || target.href || null
    }
    const fileAllowed = (path) => {
      const identity = getUserContext()
      if (identity === undefined) return true
      assertPrincipalLive(identity)
      if (canSeeAll(identity)) return true
      const emp = empOf(identity)
      const root = getWorkspaceRoot()
      return !!(path && userWorkspaces.isUserPath(emp, path, root))
    }
    const deniedStub = (displayPath) => ({
      displayPath: displayPath || '',
      targetKey: displayPath || '',
      path: displayPath || '',
      __udsAuthDenied: true,
    })
    /**
     * F09: Prefer Host FsError → serveFile maps to 403. When the Host package is
     * unavailable (unit/probe), soft-deny without leaking foreign bytes.
     */
    const softDeny = (method, displayPath = '') => {
      try {
        const { FsError } = require('@deepseek-ai/dsh-fs')
        throw new FsError('file_forbidden', 'FS_PERMISSION_DENIED')
      } catch (err) {
        if (err?.code === 'FS_PERMISSION_DENIED') throw err
      }
      if (method === 'readBytes') return new Uint8Array(0)
      if (method === 'readText') return ''
      if (method === 'stat') return undefined
      if (method === 'open') throwForbidden('file_forbidden')
      return deniedStub(displayPath)
    }
    for (const method of ['resolve', 'stat', 'readBytes', 'readText', 'open']) {
      if (typeof fs[method] !== 'function') continue
      const orig = fs[method].bind(fs)
      fs[method] = async (target, ...rest) => {
        if (target?.__udsAuthDenied) return softDeny(method, target.displayPath || '')
        if (method === 'resolve') {
          const input = typeof target === 'string' ? target : pathFromTarget(target)
          if (input && !fileAllowed(input)) return deniedStub(input)
          const resolved = await orig(target, ...rest)
          const real = pathFromTarget(resolved) || input
          if (real && !fileAllowed(real)) {
            return deniedStub(resolved?.displayPath || input || real)
          }
          return resolved
        }
        const path = pathFromTarget(target)
        if (path && !fileAllowed(path)) return softDeny(method, path)
        return orig(target, ...rest)
      }
    }
  })

  // directory picker: admin-class (live canCreateWorkspace); wrap capability() too (SEC-11)
  ctx.inject(['directoryPicker'], (dctx) => {
    const dp = dctx.directoryPicker
    if (!dp || dp.__udsAcl) return
    dp.__udsAcl = true

    const assertCanCreateWorkspace = () => {
      const identity = getUserContext()
      if (identity === undefined) return
      assertPrincipalLive(identity)
      if (!empOf(identity)) throwForbidden('login_required_workspace')
      if (!livePermissions(identity).canCreateWorkspace) {
        throwForbidden('workspace_create_forbidden')
      }
    }

    const wrapDpMethod = (obj, methodName) => {
      if (!obj || typeof obj[methodName] !== 'function') return
      const orig = obj[methodName].bind(obj)
      obj[methodName] = async (...args) => {
        assertCanCreateWorkspace()
        return orig(...args)
      }
    }

    wrapDpMethod(dp, 'pick')
    wrapDpMethod(dp, 'list')
    wrapDpMethod(dp, 'createDirectory')

    if (typeof dp.capability === 'function') {
      const origCap = dp.capability.bind(dp)
      dp.capability = (...args) => {
        assertCanCreateWorkspace()
        const cap = origCap(...args)
        if (cap && typeof cap === 'object') {
          wrapDpMethod(cap, 'list')
          wrapDpMethod(cap, 'createDirectory')
          wrapDpMethod(cap, 'pick')
        }
        return cap
      }
    }
  })

  return () => {
    for (const d of disposers) {
      try { d() } catch { /* ignore */ }
    }
  }
}
