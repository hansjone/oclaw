import { test } from 'node:test'
import assert from 'node:assert/strict'
import { MemoryStore } from '../lib/session/memory-store.js'
import { SESSION_ABSOLUTE_MAX_SECONDS } from '../lib/session/store.js'
import {
  UdsTokenMonitor,
  UDS_TOKEN_CHECK_INTERVAL_MS,
} from '../lib/uds/session-revalidation.js'

async function login(store, empNo, token, ttl = 24 * 3600) {
  const { sessionId } = await store.create({ empNo, token, authMode: 'uds-qr', isAuthenticated: true }, ttl)
  return sessionId
}

/** verify() stub: token → 'ok' | failure object | Error. Mutable via `outcomes`. */
function verifier(outcomes) {
  const calls = []
  const verify = async (empNo, token, opts) => {
    calls.push(token)
    const out = outcomes[token]
    if (out instanceof Error) throw out
    if (out === 'ok') return { empNo }
    opts?.onFailure?.(out)
    return null
  }
  return { verify, calls }
}

test('UAC token is checked every 2 hours', () => {
  assert.equal(UDS_TOKEN_CHECK_INTERVAL_MS, 2 * 60 * 60 * 1000)
})

test('a rejected UAC token is only flagged — the session is never signed out', async () => {
  const store = new MemoryStore()
  const auth = await login(store, 'u-auth', 'tok-auth')
  const biz = await login(store, 'u-biz', 'tok-biz')
  const good = await login(store, 'u-ok', 'tok-ok')
  const { verify } = verifier({
    'tok-auth': { ok: false, reason: 'http_auth', statusCode: 401 },
    'tok-biz': { ok: false, reason: 'biz_code', code: '1001' },
    'tok-ok': 'ok',
  })
  const m = new UdsTokenMonitor({ sessionStore: store, verify })
  assert.deepEqual(await m.runRound(), { checked: 3, ok: 1, rejected: 2, inconclusive: 0 })
  for (const id of [auth, biz, good]) assert.ok(await store.getBySessionId(id), 'session kept')
  assert.equal(m.isTokenRejected(auth), true)
  assert.equal(m.isTokenRejected(biz), true)
  assert.equal(m.isTokenRejected(good), false)
})

test('icenterapi outages neither flag nor clear a token', async () => {
  const store = new MemoryStore()
  const id = await login(store, 'u1', 'tok')
  const outcomes = { tok: { ok: false, reason: 'http_auth' } }
  const { verify } = verifier(outcomes)
  const m = new UdsTokenMonitor({ sessionStore: store, verify })
  await m.runRound()
  assert.equal(m.isTokenRejected(id), true)
  for (const out of [{ ok: false, reason: 'network' }, { ok: false, reason: 'http_status' }, { ok: false, reason: 'bad_json' }, new Error('reset')]) {
    outcomes.tok = out
    assert.equal((await m.runRound()).inconclusive, 1)
    assert.equal(m.isTokenRejected(id), true, 'previous verdict kept')
  }
  const fresh = await login(store, 'u2', 'tok2')
  outcomes.tok2 = { ok: false, reason: 'network' }
  await m.runRound()
  assert.equal(m.isTokenRejected(fresh), false, 'outage does not flag a healthy session')
})

test('a token that verifies again (or is refreshed) clears the flag', async () => {
  const store = new MemoryStore()
  const id = await login(store, 'u1', 'tok')
  const outcomes = { tok: { ok: false, reason: 'biz_code' } }
  const { verify } = verifier(outcomes)
  const m = new UdsTokenMonitor({ sessionStore: store, verify })
  await m.runRound()
  outcomes.tok = 'ok'
  await m.runRound()
  assert.equal(m.isTokenRejected(id), false)

  outcomes.tok = { ok: false, reason: 'http_auth' }
  await m.runRound()
  m.markRefreshed([id])
  assert.equal(m.isTokenRejected(id), false)
})

test('each empNo+token is verified once per round', async () => {
  const store = new MemoryStore()
  await login(store, 'u2', 'tok-x')
  await login(store, 'u2', 'tok-x')
  const { verify, calls } = verifier({ 'tok-x': 'ok' })
  await new UdsTokenMonitor({ sessionStore: store, verify }).runRound()
  assert.deepEqual(calls, ['tok-x'])
})

test('updateUserData writes a refreshed token in place', async () => {
  const store = new MemoryStore()
  const id = await login(store, 'u1', 'old')
  await store.updateUserData(id, { token: 'new', tokenRefreshedAt: 'now' })
  const [row] = await store.listUdsSessionsForValidation()
  assert.equal(row.sessionId, id)
  assert.equal(row.token, 'new')
})

test('"never sign out" TTL: no absolute cap, long timers do not fire early', async () => {
  const TEN_YEARS = 10 * 365 * 24 * 3600
  const store = new MemoryStore()
  const id = await login(store, 'u1', 'tok', TEN_YEARS)
  const row = store._sessions.get(id)
  assert.ok(row.absoluteExpiresAt > Date.now() + 9 * 365 * 24 * 3600 * 1000, 'cap follows the TTL, not 7 days')
  await new Promise((r) => setTimeout(r, 20))
  assert.ok(await store.getBySessionId(id), 'setTimeout overflow would have removed it already')

  // Sessions minted under the 7-day default get their cap lifted on activity.
  const old = await login(store, 'u2', 'tok2', 1800)
  assert.ok(store._sessions.get(old).absoluteExpiresAt <= Date.now() + SESSION_ABSOLUTE_MAX_SECONDS * 1000)
  await store.touch(old, TEN_YEARS)
  assert.ok(store._sessions.get(old).absoluteExpiresAt > Date.now() + 9 * 365 * 24 * 3600 * 1000)
})
