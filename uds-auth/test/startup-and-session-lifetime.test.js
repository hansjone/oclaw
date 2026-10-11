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
