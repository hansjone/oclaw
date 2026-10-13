import { test } from 'node:test'
import assert from 'node:assert/strict'
import { MemoryStore } from '../lib/session/memory-store.js'
import { SESSION_ABSOLUTE_MAX_SECONDS } from '../lib/session/store.js'
import { patchWebServerWithIdentity } from '../lib/dsh-acl.js'

test('session absolute lifetime is 7 days, independent of the 30-min idle TTL', async () => {
  assert.equal(SESSION_ABSOLUTE_MAX_SECONDS, 7 * 24 * 60 * 60)
  const store = new MemoryStore()
  const before = Date.now()
  const { sessionId, record } = await store.create({ empNo: 'administrator', authMode: 'local-admin-unlock' }, 1800)
  assert.ok(record.absoluteExpiresAt >= before + SESSION_ABSOLUTE_MAX_SECONDS * 1000)
  assert.ok(record.expiresAt <= Date.now() + 1800 * 1000)
  // Simulate 25 minutes passing, then activity: idle expiry must slide past the old 30-min mark.
  const row = store._sessions.get(sessionId)
  row.createdAt -= 25 * 60_000
  row.expiresAt -= 25 * 60_000
  row.absoluteExpiresAt -= 25 * 60_000
  const touched = await store.touch(sessionId, 1800)
  // Old min(ttl, 7d) cap left only ~5 minutes here; now the full idle window is restored.
  assert.ok(touched.expiresAt > Date.now() + 29 * 60_000, 'idle TTL slides past the old 30-min hard stop')
})

function fakeServer() {
  return {
    exact: new Map(),
    prefixes: new Map(),
    upgrades: new Map(),
    register(route) { this.prefixes.set(route.path, route) },
  }
}

function fakeRes() {
  return {
    status: null,
    body: null,
    writeHead(code) { this.status = code },
    end(body) { this.body = body },
  }
}

test('/api/* requests wait for the gateway ACL during startup instead of 403', async () => {
  const server = fakeServer()
  let ready = false
  let handled = 0
  server.register({ kind: 'prefix', path: '/api', handler: async () => { handled++ } })
  patchWebServerWithIdentity(server, async () => null, () => null, () => (
    ready ? { ok: true } : { ok: false, reason: 'gateway_acl_not_ready' }
  ))
  setTimeout(() => { ready = true }, 150)
  const res = fakeRes()
  const req = { url: '/api/settings/describe', method: 'POST', headers: { host: '127.0.0.1:1' } }
  await server.prefixes.get('/api').handler(req, res)
  assert.equal(handled, 1, 'request proceeded once the ACL was installed')
  assert.equal(res.status, null)
})

test('other origin/host rejections still fail immediately', async () => {
  const server = fakeServer()
  let handled = 0
  server.register({ kind: 'prefix', path: '/api', handler: async () => { handled++ } })
  patchWebServerWithIdentity(server, async () => null, () => null, () => ({ ok: false, reason: 'host_not_trusted' }))
  const res = fakeRes()
  const started = Date.now()
  await server.prefixes.get('/api').handler({ url: '/api/x', method: 'POST', headers: {} }, res)
  assert.equal(res.status, 403)
  assert.equal(handled, 0)
  assert.ok(Date.now() - started < 1000)
})

test('session-status probe is routed outside the auth middleware and never slides the TTL', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(new URL('../lib/index.js', import.meta.url), 'utf8')
  const probe = src.indexOf("pathname === '/uds-auth/session-status'")
  const authed = src.indexOf("if (pathname.startsWith('/uds-auth/api/')) {")
  assert.ok(probe > 0 && probe < authed, 'probe answers before /uds-auth/api/* auth dispatch')
  const body = src.slice(src.indexOf('async function handleSessionStatus'), src.indexOf('// 客户端 config.get'))
  assert.doesNotMatch(body, /touch\(|_authMiddleware/)

  // getByBearer (what the probe uses) must not slide the idle TTL.
  const store = new MemoryStore()
  const { sessionId, bearer } = await store.create({ empNo: 'u1' }, 1800)
  const before = store._sessions.get(sessionId).expiresAt
  await new Promise((r) => setTimeout(r, 5))
  assert.ok(await store.getByBearer(bearer))
  assert.equal(store._sessions.get(sessionId).expiresAt, before)
})

test('client signs out on confirmed idle expiry instead of prompting on every call', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(new URL('../lib/client.js', import.meta.url), 'utf8')
  // Expiry is only acted on after the non-sliding probe says alive=false.
  assert.match(src, /fetch\('\/uds-auth\/session-status'/)
  assert.match(src, /data\.alive === false && isLoggedInInUi\(\)\) \{\s*window\.dispatchEvent\(new Event\('uds-auth-expired'\)\)/)
  // RPC failures and HTTP 401s trigger the probe; an idle timer and focus do too.
  assert.match(src, /looksLikeSessionGone\(result\.error\)\) \{\s*void checkSessionAlive\(\)/)
  assert.match(src, /if \(res\.status === 401\) void checkSessionAlive\(\)/)
  assert.match(src, /setInterval\(check, 60_000\)/)
  // Expired sign-out skips /api/logout and tells the user why.
  assert.match(src, /signOut\(\{ expired: true \}\)/)
  assert.match(src, /sessionExpired \? t\('ui\.sessionExpiredSignedOut'\)/)
})

test('QR refresh renews the UAC token in place instead of minting a new session', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(new URL('../lib/index.js', import.meta.url), 'utf8')
  // refresh flag is read locally and never forwarded upstream (body is rebuilt from contract fields).
  assert.match(src, /const refreshToken = parsedBody\.refresh === true/)
  const branch = src.slice(src.indexOf('if (refreshToken) {'), src.indexOf("const role = await _authMiddleware.resolveRoleOnLogin(id)\n          const now"))
  assert.match(branch, /peekCallerSession\(req\)/)
  assert.match(branch, /token_refresh_emp_mismatch/)
  assert.match(branch, /refreshSessionToken\(id, credentials\.token, profile\)/)
  assert.doesNotMatch(branch, /mintLoginSession|appendSessionCookie/)
  // Default: no automatic sign-out; token rejections are flagged, not revoked.
  assert.match(src, /sessionIdleTimeoutHours: 0,/)
  assert.match(src, /tokenValid: session \? !_tokenMonitor\?\.isTokenRejected\(session\.sessionId\) : null/)
  assert.doesNotMatch(src, /revokeInvalidUdsAccount|UdsSessionRevalidator/)
})

test('client prompts a refresh QR on token expiry without signing out', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(new URL('../lib/client.js', import.meta.url), 'utf8')
  assert.match(src, /new Event\(data\.tokenValid \? 'uds-auth-token-ok' : 'uds-auth-token-expired'\)/)
  // expiry opens the panel once; the token handler never calls signOut
  const handler = src.slice(src.indexOf('const onTokenExpired = () => {'), src.indexOf('const onTokenOk = () => {'))
  assert.match(handler, /setOpen\(true\)/)
  assert.doesNotMatch(handler, /signOut/)
  assert.match(src, /refreshing \? \{ qrCodeKey, qrCodeValue, refresh: true \}/)
  assert.match(src, /if \(auth\?\.success && auth\.refreshed\) \{/)
  assert.match(src, /const wantQr = open && loginMode === 'qr' && \(!user \|\| tokenExpired\)/)
})
