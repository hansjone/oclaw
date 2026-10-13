import { test } from 'node:test'
import assert from 'node:assert/strict'
import { RolesStore } from '../lib/roles.js'
import { MemoryStore } from '../lib/session/memory-store.js'
import { SessionBridgeStore } from '../lib/session-bridge.js'
import { UserWorkspaceStore } from '../lib/workspace-provision.js'
import {
  extractSessionBearer,
  extractSessionBearerAsync,
} from '../lib/session/request-auth.js'
import {
  installDshAcl,
  identityFromSessionRecord,
  resolveIdentityFromRequest,
  resolveIdentityFromRequestSync,
} from '../lib/dsh-acl.js'
import { runWithUserContext } from '../lib/context.js'
import { installGatewayPolicy } from '../lib/gateway-policy.js'
import { createAuthMiddleware } from '../lib/middleware/auth-middleware.js'
import { buildLocalAdminUserContext, sealLocalAdminBox } from '../lib/local-admin.js'

process.env.UDS_AUTH_LOCAL_ADMIN_BOX = sealLocalAdminBox('test-passphrase-ok')

const STALE = 'deadbeef'.repeat(8)

const EMERGENCY_LOGINS = [
  ['password fallback', 'fallback', () => ({
    empNo: 'administrator',
    username: 'Fallback Administrator',
    isAuthenticated: true,
    role: 'fallback_admin',
    authMode: 'fallback-password',
    fallbackCredVersion: 1,
  })],
  ['sealed box', 'sealed_box', () => buildLocalAdminUserContext()],
]

function makeStores() {
  const roles = new RolesStore({})
  roles._fallbackPasswordHash = 'scrypt$test'
  roles._fallbackCredVersion = 1
  roles._prefs.set('administrator', { viewAllSessions: true })
  return { roles, sessionStore: new MemoryStore(), sessionBridge: new SessionBridgeStore({}) }
}

async function login(stores, userContext, kind) {
  const { bearer } = await stores.sessionStore.create(userContext, 1800)
  const bridge = stores.sessionBridge.mint({ empNo: userContext.empNo, kind, token: bearer })
  return { bearer, bridge }
}

function muxUpgrade(query, headers = {}) {
  return {
    method: 'GET',
    url: '/api/remote.mux?' + query,
    socket: { remoteAddress: '127.0.0.1' },
    headers: { upgrade: 'websocket', connection: 'Upgrade', origin: 'dsh-app://app', ...headers },
  }
}

for (const [label, kind, buildContext] of EMERGENCY_LOGINS) {
  test(`${label}: stale UDS_SESSION cookie no longer shadows the WS ticket`, async () => {
    const stores = makeStores()
    const { bearer } = await login(stores, buildContext(), kind)
    const deps = { ...stores, rolesStore: stores.roles }
    const cookie = { cookie: `UDS_SESSION=${STALE}` }

    const t1 = stores.sessionBridge.mintWsTicket({ empNo: 'administrator', bearer })
    const sync = resolveIdentityFromRequestSync(muxUpgrade('udsWsTicket=' + t1.ticket, cookie), deps)
    assert.equal(sync?.empNo, 'administrator')
    assert.equal(sync?.kind, kind)

    const t2 = stores.sessionBridge.mintWsTicket({ empNo: 'administrator', bearer })
    const asyncId = await resolveIdentityFromRequest(muxUpgrade('udsWsTicket=' + t2.ticket, cookie), deps)
    assert.equal(asyncId?.empNo, 'administrator')
    assert.equal(asyncId?.kind, kind)
  })

  test(`${label}: stale cookie + loopback bridge query still authenticates remote.mux`, async () => {
    const stores = makeStores()
    const { bridge } = await login(stores, buildContext(), kind)
    const req = muxUpgrade(
      `udsBridgeEmpNo=administrator&udsBridgeToken=${bridge.token}&udsBridgeKind=${kind}`,
      { cookie: `UDS_SESSION=${STALE}` },
    )
    const id = resolveIdentityFromRequestSync(req, { ...stores, rolesStore: stores.roles })
    assert.equal(id?.empNo, 'administrator')
  })

  test(`${label}: workspace follow shows every workspace (view-all on)`, async () => {
    const stores = makeStores()
    const { bearer } = await login(stores, buildContext(), kind)
    const identity = identityFromSessionRecord(stores.sessionStore.getByBearerSync(bearer), stores.roles)
    const { wc } = installFollowHarness(stores)
    const frames = await collect(wc, identity)
    assert.deepEqual(frames[0].value.items.map((w) => w.id), ['ws-admin', 'ws-shared'])
  })
}

test('live cookie still wins and the WS ticket is not consumed', async () => {
  const stores = makeStores()
  const a = await login(stores, buildLocalAdminUserContext(), 'sealed_box')
  const b = await login(stores, { empNo: '1001', authMode: 'token+profile' }, 'uds')
  const ticket = stores.sessionBridge.mintWsTicket({ empNo: '1001', bearer: b.bearer })
  const req = muxUpgrade('udsWsTicket=' + ticket.ticket, { cookie: `UDS_SESSION=${a.bearer}` })
  const got = extractSessionBearer(req, {
    sessionBridge: stores.sessionBridge,
    isLiveBearer: (x) => !!stores.sessionStore.getByBearerSync(x),
  })
  assert.equal(got.via, 'cookie')
  assert.equal(got.bearer, a.bearer)
  assert.ok(stores.sessionBridge.consumeWsTicket(ticket.ticket), 'ticket left unconsumed')
})

test('dead cookie with no other credential keeps legacy cookie result', async () => {
  const req = { method: 'GET', url: '/uds-auth/api/me', headers: { cookie: `UDS_SESSION=${STALE}` } }
  const got = await extractSessionBearerAsync(req, {
    sessionBridge: new SessionBridgeStore({}),
    isLiveBearer: async () => false,
  })
  assert.deepEqual(got, { bearer: STALE, via: 'cookie' })
})

test('auth middleware: stale cookie falls through to bridge headers for /api/me', async () => {
  const stores = makeStores()
  const { bridge } = await login(stores, buildLocalAdminUserContext(), 'sealed_box')
  const mw = createAuthMiddleware({
    udsAuth: { baseUrl: 'https://uac.example.test', systemCode: 'test' },
    session: { cookieMaxAge: 1_800_000, slidingExpiration: true },
  }, stores.sessionStore, stores.roles, { sessionBridge: stores.sessionBridge })
  const ctx = {
    req: {
      method: 'GET',
      url: '/uds-auth/api/me',
      socket: { remoteAddress: '127.0.0.1' },
      headers: {
        cookie: `UDS_SESSION=${STALE}`,
        'x-uds-bridge-empno': 'administrator',
        'x-uds-bridge-token': bridge.token,
        'x-uds-bridge-kind': 'sealed_box',
      },
    },
    res: { setHeader() {}, getHeader() {} },
  }
  await mw(ctx, async () => {})
  assert.equal(ctx.empNo, 'administrator')
  assert.equal(ctx.authKind, 'sealed_box')
  assert.equal(ctx.permissions.canViewAllSessions, true)
})

test('auth middleware slides bridge expiry with the session', async () => {
  const stores = makeStores()
  const { bridge } = await login(stores, buildLocalAdminUserContext(), 'sealed_box')
  const row = stores.sessionBridge._byToken.get(bridge.token)
  row.exp = Date.now() + 5_000
  const mw = createAuthMiddleware({
    udsAuth: { baseUrl: 'https://uac.example.test', systemCode: 'test' },
    session: { cookieMaxAge: 1_800_000, slidingExpiration: true },
  }, stores.sessionStore, stores.roles, { sessionBridge: stores.sessionBridge })
  const ctx = {
    req: {
      method: 'GET',
      url: '/uds-auth/api/me',
      headers: { 'x-uds-bridge-empno': 'administrator', 'x-uds-bridge-token': bridge.token },
    },
    res: { setHeader() {}, getHeader() {} },
  }
  await mw(ctx, async () => {})
  assert.equal(ctx.empNo, 'administrator')
  assert.ok(row.exp > Date.now() + 25 * 60_000, 'bridge exp extended to ~30min')
})

test('SessionBridgeStore.touch never revives an expired bridge', () => {
  const store = new SessionBridgeStore({ ttlMs: 60_000 })
  const live = store.mint({ empNo: 'administrator', kind: 'sealed_box' })
  const dead = store.mint({ empNo: 'administrator', kind: 'sealed_box' })
  store._byToken.get(dead.token).exp = Date.now() - 1
  assert.equal(store.touch(live.token, 600_000), true)
  assert.ok(store._byToken.get(live.token).exp > Date.now() + 500_000)
  assert.equal(store.touch(dead.token, 600_000), false)
  assert.equal(store.verify('administrator', dead.token), null)
  assert.equal(store.touch('unknown'), false)
})

test('gateway lets anonymous workspace/follow reach dsh-acl (empty baseline, not an error)', async () => {
  let principal = null
  const descriptors = {
    'workspace/follow': { namespace: 'workspace', method: 'follow', parameters: [], invocation: { kind: 'direct' }, mode: 'stream' },
    'session/list': { namespace: 'session', method: 'list', parameters: [], invocation: { kind: 'direct' } },
  }
  const gateway = {
    async *openRemoteEvents() {}, receiveRemoteEventResult() {},
    resolveDescriptor(ns, method) { return descriptors[`${ns}/${method}`] },
    async prepareInvocation(request) {
      if (request.method === 'follow') {
        return { method: async function* () { yield { type: 'baseline', value: { items: [] } } } }
      }
      return { method: () => 'ok' }
    },
  }
  installGatewayPolicy(gateway, {
    identity: () => principal,
    assertPrincipal: (p) => { if (!p?.empNo) throw new Error('login_required_session') },
    permissions: () => ({ canAccessSettings: false }),
    assertSession: () => {},
    deny: (code) => { throw new Error(code) },
  })
  const prepared = await gateway.prepareInvocation({ namespace: 'workspace', method: 'follow', args: {} })
  const frames = []
  for await (const f of prepared.method()) frames.push(f)
  assert.equal(frames[0].type, 'baseline')
  // Other endpoints stay locked for anonymous principals.
  await assert.rejects(
    gateway.prepareInvocation({ namespace: 'session', method: 'list', args: {} }),
    /login_required_session/,
  )
  principal = {}
  await assert.doesNotReject(gateway.prepareInvocation({ namespace: 'workspace', method: 'follow', args: {} }))
})

test('dsh-acl follow: anonymous gets one empty baseline and holds until abort', async () => {
  const stores = makeStores()
  const { wc } = installFollowHarness(stores)
  const ac = new AbortController()
  const frames = []
  const done = runWithUserContext(null, async () => {
    for await (const f of wc.follow(ac.signal)) frames.push(f)
  })
  await new Promise((r) => setTimeout(r, 20))
  assert.equal(frames.length, 1)
  assert.deepEqual(frames[0].value.items, [])
  ac.abort()
  await done
})

function installFollowHarness(stores) {
  const items = [
    { id: 'ws-admin', workspaceId: 'ws-admin', path: 'C:/u/administrator', sessionIds: [] },
    { id: 'ws-shared', workspaceId: 'ws-shared', path: 'D:/project/harness', sessionIds: ['s1'] },
  ]
  const uw = new UserWorkspaceStore({})
  uw.set('administrator', { path: 'C:/u/administrator', workspaceId: 'ws-admin' })
  const noop = async () => {}
  const wc = {
    create: noop, rename: noop, delete: noop, insertBefore: noop, insertSessionBefore: noop,
    archiveSession: noop, unarchiveSession: noop, pinSession: noop, unpinSession: noop,
    async *follow() {
      yield { type: 'baseline', value: { items, archivedSessionIds: [], pinnedSessionIds: [] } }
    },
  }
  installDshAcl({
    inject(deps, cb) { if (deps.includes('workspaceController')) cb({ workspaceController: wc }) },
    on() { return () => {} },
    get() { throw new Error('no service') },
  }, {
    sessionAcl: { getOwner: () => null, setOwner() {} },
    userWorkspaces: uw,
    getWorkspaceRoot: () => '',
    getRolesStore: () => stores.roles,
    getSessionStore: () => stores.sessionStore,
    ensureUserWorkspace: async () => ({ workspaceId: 'ws-admin' }),
    getWorkspaceRegistry: () => ({ list: () => items, get: (id) => items.find((i) => i.id === id) }),
  })
  return { wc, items }
}

async function collect(wc, identity) {
  const frames = []
  await runWithUserContext(identity, async () => {
    for await (const f of wc.follow(new AbortController().signal)) frames.push(f)
  })
  return frames
}

test('client emits connection/reset after login so boot-time caches (settings mirror) reload', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(new URL('../lib/client.js', import.meta.url), 'utf8')
  // connection.reconnect() alone never emits connection/reset (DSH only emits it on onConnected).
  assert.match(src, /window\.__udsAuthEmitReset = \(\) => \{\s*try \{ cctx\.emit\('connection\/reset'\) \}/)
  assert.match(src, /function scheduleAuthReset\(/)
  // fires after a soft reconnect and on the first authenticated /api/me per empNo
  assert.match(src, /_softReconnectQuietUntil = Date\.now\(\) \+ 2800\s*\n\s*scheduleAuthReset\(/)
  assert.match(src, /window\.__udsAuthResetEmp !== resetEmp/)
  // cleared on logout / unauthenticated so the next login resets again
  assert.equal((src.match(/window\.__udsAuthResetEmp = null/g) || []).length, 2)
})

test('anonymous workspace/initializeDefault is a no-op (no default-workspace error toast)', async () => {
  let principal = null
  let invoked = 0
  const gateway = {
    async *openRemoteEvents() {}, receiveRemoteEventResult() {},
    resolveDescriptor: (namespace, method) => ({ namespace, method, parameters: [], invocation: { kind: 'direct' } }),
    async prepareInvocation() { return { method: () => { invoked++; return { workspace: { workspaceId: 'w' } } } } },
  }
  installGatewayPolicy(gateway, {
    identity: () => principal,
    assertPrincipal: (p) => { if (!p?.empNo) throw new Error('login_required_session') },
    permissions: () => ({ canAccessSettings: true }),
    assertSession: () => {},
    deny: (code) => { throw new Error(code) },
  })
  const anon = await gateway.prepareInvocation({ namespace: 'workspace', method: 'initializeDefault', args: {} })
  assert.equal(anon.method(), undefined)
  assert.equal(invoked, 0, 'real controller never runs for anonymous callers')
  principal = { empNo: 'administrator' }
  const authed = await gateway.prepareInvocation({ namespace: 'workspace', method: 'initializeDefault', args: {} })
  assert.deepEqual(authed.method(), { workspace: { workspaceId: 'w' } })
  assert.equal(invoked, 1)
  principal = null
  await assert.rejects(
    gateway.prepareInvocation({ namespace: 'workspace', method: 'create', args: {} }),
    /login_required_session/,
  )
})

test('anonymous stream endpoints are parked until the carrier aborts (no terminal error)', async () => {
  let principal = null
  let invoked = 0
  const control = new AbortController()
  const gateway = {
    async *openRemoteEvents() {}, receiveRemoteEventResult() {},
    resolveDescriptor: (namespace, method) => ({ namespace, method, parameters: [], invocation: { kind: 'direct' }, mode: 'stream' }),
    async prepareInvocation() {
      return {
        invocation: { signal: control.signal },
        method: async function* () { invoked++; yield { status: 'credential-stored' } },
      }
    },
  }
  installGatewayPolicy(gateway, {
    identity: () => principal,
    assertPrincipal: (p) => { if (!p?.empNo) throw new Error('login_required_session') },
    permissions: () => ({ canAccessSettings: true }),
    assertSession: () => {},
    deny: (code) => { throw new Error(code) },
  })
  const prepared = await gateway.prepareInvocation({ namespace: 'account', method: 'watch', args: {} })
  const it = prepared.method()[Symbol.asyncIterator]()
  let settled = false
  const next = it.next().then((r) => { settled = true; return r })
  await new Promise((r) => setTimeout(r, 30))
  assert.equal(settled, false, 'anonymous stream yields nothing and does not fail')
  control.abort()
  assert.deepEqual(await next, { value: undefined, done: true })
  assert.equal(invoked, 0, 'real stream never opened for anonymous callers')

  principal = { empNo: 'administrator' }
  const authed = await gateway.prepareInvocation({ namespace: 'account', method: 'watch', args: {} })
  const frames = []
  for await (const f of authed.method()) frames.push(f)
  assert.deepEqual(frames, [{ status: 'credential-stored' }])
})

test('WS activity (assertPrincipalLive) reports the live session so its idle TTL slides', async () => {
  const stores = makeStores()
  const [, kind, ctxOf] = EMERGENCY_LOGINS[0]
  const { bearer } = await login(stores, ctxOf(), kind)
  const session = await stores.sessionStore.getByBearer(bearer)
  const seen = []
  const noop = async () => {}
  const wc = {
    create: noop, rename: noop, delete: noop, insertBefore: noop, insertSessionBefore: noop,
    archiveSession: noop, unarchiveSession: noop, pinSession: noop, unpinSession: noop,
    async *follow() { yield { type: 'baseline', value: { items: [], archivedSessionIds: [], pinnedSessionIds: [] } } },
  }
  installDshAcl({
    inject(deps, cb) { if (deps.includes('workspaceController')) cb({ workspaceController: wc }) },
    on() { return () => {} },
    get() { throw new Error('no service') },
  }, {
    sessionAcl: { getOwner: () => null, setOwner() {} },
    userWorkspaces: new UserWorkspaceStore({}),
    getWorkspaceRoot: () => '',
    getRolesStore: () => stores.roles,
    getSessionStore: () => stores.sessionStore,
    ensureUserWorkspace: async () => ({ workspaceId: 'ws-admin' }),
    getWorkspaceRegistry: () => ({ list: () => [], get: () => null }),
    onPrincipalActive: (sid, emp) => seen.push([sid, emp]),
  })
  await collect(wc, identityFromSessionRecord(session, stores.roles))
  assert.deepEqual(seen[0], [session.sessionId, 'administrator'])
})

test('SessionBridgeStore.touchEmpNo slides every live bridge of that account only', () => {
  const store = new SessionBridgeStore({ ttlMs: 60_000 })
  const a = store.mint({ empNo: 'alice', kind: 'uds' })
  const b = store.mint({ empNo: 'bob', kind: 'uds' })
  store.touchEmpNo('alice', 10 * 60_000)
  assert.ok(store._byToken.get(a.token).exp > Date.now() + 5 * 60_000)
  assert.ok(store._byToken.get(b.token).exp <= Date.now() + 60_000)
})
