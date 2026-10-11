/**
 * Phase-1 P0 negative tests (SEC-01..06, partial 07-09).
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { createHash } from 'node:crypto'
import { MemoryStore } from '../lib/session/memory-store.js'
import { SESSION_COOKIE } from '../lib/session/store.js'
import {
  extractSessionBearer,
  extractPortalCredentials,
  buildSessionCookie,
} from '../lib/session/request-auth.js'
import { createAuthMiddleware } from '../lib/middleware/auth-middleware.js'
import {
  resolveIdentityFromRequest,
  resolveIdentityFromRequestSync,
} from '../lib/dsh-acl.js'
import { requestIsLoopback } from '../lib/skill-credentials.js'
import { createAgentAuthHandlers } from '../lib/agent-auth.js'
import { RolesStore, ROLES, DEFAULT_FALLBACK_PASSWORD } from '../lib/roles.js'
import { SessionBridgeStore } from '../lib/session-bridge.js'
import { peekBrowserIdentity, rememberBrowserIdentity } from '../lib/identity-cache.js'

function mockRoles(seed = {}) {
  const store = new RolesStore({})
  for (const [empNo, role] of Object.entries(seed)) {
    store._roles.set(empNo, role)
  }
  return store
}

test('SEC-01: static generic handlers are not exported from index route helpers', async () => {
  // Regression: makeStaticHandler / open path resolve must not exist.
  const src = await import('node:fs/promises').then((fs) =>
    fs.readFile(new URL('../lib/index.js', import.meta.url), 'utf-8'),
  )
  assert.equal(src.includes('makeStaticHandler'), false)
  assert.equal(src.includes('handleQrcodeStatic'), false)
  assert.equal(src.includes('handleVendorStatic'), false)
  assert.match(src, /static file routes removed/)
})

test('SEC-02/04: MemoryStore keys by bearer — empNo alone cannot prove auth', async () => {
  const store = new MemoryStore()
  const { bearer, sessionId } = await store.create({
    empNo: '10001',
    username: 'Alice',
    isAuthenticated: true,
    token: 'upstream-secret',
  }, 600)
  assert.ok(bearer.length >= 32)
  assert.ok(sessionId)

  const byBearer = await store.getByBearer(bearer)
  assert.equal(byBearer.empNo, '10001')
  assert.equal(store.getByBearerSync(bearer).empNo, '10001')

  assert.equal(await store.getByBearer('deadbeef'.repeat(8)), null)
  assert.equal(await store.getByBearer(''), null)

  // Profile-like get(empNo) must not be treated as auth by middleware (documented).
  const cached = await store.get('10001')
  assert.equal(cached.empNo, '10001')
  assert.ok(cached.token, 'cache may hold token but must not grant request auth alone')
})

test('SEC-02: fallback USER/UI cookies are not session bearers', () => {
  const req = {
    headers: {
      cookie: 'UDS_FALLBACK_USER=administrator; UDS_FALLBACK_UI=administrator',
    },
  }
  assert.equal(extractSessionBearer(req), null)
  assert.equal(extractPortalCredentials(req), null)
})

test('SEC-02/03: sync/async ACL identity requires verified local session', async () => {
  const store = new MemoryStore()
  const roles = mockRoles({ administrator: ROLES.FALLBACK_ADMIN, '10001': ROLES.SUPER_ADMIN })
  const deps = { sessionStore: store, rolesStore: roles, sessionBridge: null }

  // Forged fallback cookies + arbitrary portal token → no principal
  const forged = {
    headers: {
      cookie: 'UDS_FALLBACK_USER=administrator; PORTALSSOUser=10001; PORTALSSOCookie=arbitrary',
    },
  }
  assert.equal(resolveIdentityFromRequestSync(forged, deps), null)
  assert.equal(await resolveIdentityFromRequest(forged, deps), null)

  // EmpNo cache hit alone is not enough
  await store.create({ empNo: '10001', username: 'A', isAuthenticated: true }, 600)
  assert.equal(resolveIdentityFromRequestSync({
    headers: { cookie: 'PORTALSSOUser=10001' },
  }, deps), null)

  // Valid bearer → principal (no upstream token on identity)
  const { bearer } = await store.create({
    empNo: '10001',
    username: 'A',
    token: 'uac-secret',
    isAuthenticated: true,
  }, 600)
  const req = { headers: { cookie: `${SESSION_COOKIE}=${bearer}` } }
  const sync = resolveIdentityFromRequestSync(req, deps)
  assert.equal(sync.empNo, '10001')
  assert.equal(sync.userContext.token, undefined)
  const asyncId = await resolveIdentityFromRequest(req, deps)
  assert.equal(asyncId.empNo, '10001')
  assert.equal(asyncId.userContext.token, undefined)
})

test('SEC-03: ACL path does not bootstrap first user', async () => {
  const store = new MemoryStore()
  const roles = mockRoles({}) // empty
  const { bearer } = await store.create({
    empNo: 'attacker00001',
    isAuthenticated: true,
  }, 600)
  const identity = await resolveIdentityFromRequest({
    headers: { cookie: `${SESSION_COOKIE}=${bearer}` },
  }, { sessionStore: store, rolesStore: roles })
  assert.equal(identity.empNo, 'attacker00001')
  assert.equal(roles.isEmpty(), true, 'roles table must stay empty')
  assert.equal(identity.role, ROLES.USER)
})

test('SEC-04: two devices — wrong bearer / mismatched bridge rejected', async () => {
  const store = new MemoryStore()
  const bridge = new SessionBridgeStore({ ttlMs: 60_000 })
  const a = await store.create({ empNo: 'A', isAuthenticated: true }, 600)
  const b = await store.create({ empNo: 'B', isAuthenticated: true }, 600)
  bridge.mint({ empNo: 'A', kind: 'uds', token: a.bearer })
  bridge.mint({ empNo: 'B', kind: 'uds', token: b.bearer })

  // A bearer with B empNo bridge headers
  const bad = extractSessionBearer({
    headers: {
      'x-uds-bridge-empno': 'B',
      'x-uds-bridge-token': a.bearer,
      'x-uds-bridge-kind': 'uds',
    },
  }, { sessionBridge: bridge })
  // verify fails (empNo mismatch) → null
  assert.equal(bad, null)

  const ok = extractSessionBearer({
    headers: {
      cookie: buildSessionCookie(a.bearer, 600),
    },
  }, { sessionBridge: bridge })
  assert.equal(ok.bearer, a.bearer)
  assert.equal((await store.getByBearer(ok.bearer)).empNo, 'A')
})

test('SEC-05: requestIsLoopback ignores X-Forwarded-For', () => {
  assert.equal(requestIsLoopback({
    socket: { remoteAddress: '10.1.2.3' },
    headers: { 'x-forwarded-for': '127.0.0.1' },
  }), false)
  assert.equal(requestIsLoopback({
    socket: { remoteAddress: '127.0.0.1' },
    headers: {},
  }), true)
  assert.equal(requestIsLoopback({
    socket: { remoteAddress: '::ffff:127.0.0.1' },
    headers: { 'x-forwarded-for': '8.8.8.8' },
  }), true)
})

test('SEC-05: agent-credentials rejects empNo-only and disables raw token by default', async () => {
  const handlers = createAgentAuthHandlers({
    resolveCredentialsForSession: async () => ({ empNo: 'A', token: 't' }),
    getSessionOwner: () => 'A',
    resolveCallerSession: async () => null,
    allowRawTokenResponse: false,
  })
  const res = {
    statusCode: 0,
    headers: {},
    body: '',
    setHeader(k, v) { this.headers[k] = v },
    end(s) { this.body = s },
  }
  await handlers.handleAgentCredentials({
    method: 'POST',
    socket: { remoteAddress: '127.0.0.1' },
    headers: {},
    async *[Symbol.asyncIterator]() { yield Buffer.from(JSON.stringify({ empNo: 'A' })) },
  }, res)
  assert.equal(res.statusCode, 403)
  assert.match(res.body, /raw_token_disabled|error/)
})

test('SEC-05: outbound requires caller session matching session owner', async () => {
  let called = false
  const handlers = createAgentAuthHandlers({
    resolveCredentialsForSession: async () => {
      called = true
      return { empNo: 'A', token: 't' }
    },
    getSessionOwner: (sid) => (sid === 'sess-a' ? 'A' : 'B'),
    resolveCallerSession: async () => ({ empNo: 'A', sessionId: 'local' }),
    allowRawTokenResponse: true,
    outboundHosts: ['example.com'],
  })
  const res = {
    statusCode: 0,
    headers: {},
    body: '',
    setHeader(k, v) { this.headers[k] = v },
    end(s) { this.body = s },
  }
  // Caller A + session owned by B
  await handlers.handleOutbound({
    method: 'POST',
    socket: { remoteAddress: '127.0.0.1' },
    headers: {},
    async *[Symbol.asyncIterator]() {
      yield Buffer.from(JSON.stringify({
        sessionId: 'sess-b',
        url: 'https://example.com/x',
        empNo: 'B',
      }))
    },
  }, res)
  assert.equal(res.statusCode, 401)
  assert.equal(called, false)
})

test('SEC-06: identity-cache never restores a principal', () => {
  rememberBrowserIdentity({ empNo: 'admin', role: 'super_admin' })
  assert.equal(peekBrowserIdentity(), null)
})

test('SEC-08: new RolesStore does not enable shared default password', async () => {
  const store = new RolesStore({})
  await store.init()
  assert.equal(store.isFallbackEnabled(), false)
  assert.equal(store.verifyFallback(DEFAULT_FALLBACK_PASSWORD, '127.0.0.1'), false)
})

test('SEC-09: empty roles + non-initial admin cannot bootstrap via middleware helper', async () => {
  const store = new MemoryStore()
  const roles = mockRoles({})
  const mw = createAuthMiddleware({
    userSearchUrl: 'http://127.0.0.1:9/never',
    initialAdminEmpNo: '99999',
    allowOpenRegistration: true,
    udsAuth: { baseUrl: 'http://127.0.0.1:9' },
    session: { cookieMaxAge: 600000, slidingExpiration: true },
  }, store, roles, {})
  await assert.rejects(
    () => mw.resolveRoleOnLogin('11111'),
    (err) => err.code === 'bootstrap_required',
  )
  const role = await mw.resolveRoleOnLogin('99999')
  assert.equal(role, ROLES.SUPER_ADMIN)
  assert.equal(roles.getRole('99999'), ROLES.SUPER_ADMIN)
})

test('SEC-07: session cookie helper is HttpOnly', () => {
  const c = buildSessionCookie('abc123def456abc123def456abc123de', 600, { secure: false })
  assert.match(c, /^UDS_SESSION=/)
  assert.match(c, /HttpOnly/)
  assert.match(c, /SameSite=Lax/)
})

test('bearer hash is not reversible from store maps', async () => {
  const store = new MemoryStore()
  const { bearer } = await store.create({ empNo: 'x', isAuthenticated: true }, 60)
  const hash = createHash('sha256').update(bearer).digest('hex')
  assert.ok(store._byBearer.has(hash))
  assert.equal([...store._byBearer.keys()].includes(bearer), false)
})
