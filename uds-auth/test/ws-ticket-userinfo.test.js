import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { SessionBridgeStore } from '../lib/session-bridge.js'
import { extractSessionBearer } from '../lib/session/request-auth.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')

test('T01: WS ticket is single-use and extractSessionBearer consumes it', () => {
  const bridge = new SessionBridgeStore({})
  const minted = bridge.mintWsTicket({ empNo: 'A001', bearer: 'b'.repeat(32), ttlMs: 60_000 })
  assert.ok(minted.ticket)
  const req = {
    method: 'GET', url: '/api/remote.mux?udsWsTicket=' + minted.ticket,
    headers: { upgrade: 'websocket', connection: 'keep-alive, Upgrade' },
  }
  const first = extractSessionBearer(req, { sessionBridge: bridge })
  assert.equal(first?.via, 'ws_ticket')
  assert.equal(first?.bearer, 'b'.repeat(32))
  const replay = extractSessionBearer(req, { sessionBridge: bridge })
  assert.equal(replay, null)
  assert.equal(bridge.consumeWsTicket(minted.ticket), null)
})

test('T01/0.3.9: Upgrade: websocket alone is enough (Connection may be absent on Desktop)', () => {
  const bridge = new SessionBridgeStore({})
  const minted = bridge.mintWsTicket({ empNo: 'A001', bearer: 'b'.repeat(32), ttlMs: 60_000 })
  const req = {
    method: 'GET', url: '/api/remote.mux?udsWsTicket=' + minted.ticket,
    headers: { upgrade: 'websocket' },
  }
  const first = extractSessionBearer(req, { sessionBridge: bridge })
  assert.equal(first?.via, 'ws_ticket')
  assert.equal(first?.bearer, 'b'.repeat(32))
})

test('D07: WS ticket is ignored on normal HTTP (no upgrade)', () => {
  const bridge = new SessionBridgeStore({})
  const minted = bridge.mintWsTicket({ empNo: 'A001', bearer: 'b'.repeat(32), ttlMs: 60_000 })
  const req = { url: '/uds-auth/api/config?udsWsTicket=' + minted.ticket, headers: {} }
  assert.equal(extractSessionBearer(req, { sessionBridge: bridge }), null)
  assert.ok(bridge.consumeWsTicket(minted.ticket))
})

test('T01: client prefers udsWsTicket; loopback bridge query is Desktop fallback', () => {
  const src = readFileSync(join(root, 'lib/client.js'), 'utf8')
  assert.match(src, /udsWsTicket/)
  assert.match(src, /mintWsTicketSync/)
  assert.match(src, /udsBridgeToken/)
  assert.match(src, /0\.3\.9 Desktop path/)
  const auth = readFileSync(join(root, 'lib/session/request-auth.js'), 'utf8')
  assert.match(auth, /bridge_query/)
  assert.match(auth, /requestIsLoopback/)
})

test('Desktop loopback WS upgrade accepts udsBridge query when ticket missing', () => {
  const bridge = new SessionBridgeStore({})
  const token = 'c'.repeat(32)
  bridge.mint({ empNo: 'administrator', kind: 'sealed_box', token })
  const req = {
    method: 'GET',
    url: '/api/remote.mux?udsBridgeEmpNo=administrator&udsBridgeToken=' + token,
    headers: { upgrade: 'websocket' },
    socket: { remoteAddress: '127.0.0.1' },
  }
  const got = extractSessionBearer(req, { sessionBridge: bridge })
  assert.equal(got?.via, 'bridge_query')
  assert.equal(got?.bearer, token)
  // Off-loopback must not accept bridge query (even with upgrade).
  const remote = {
    ...req,
    socket: { remoteAddress: '8.8.8.8' },
  }
  assert.equal(extractSessionBearer(remote, { sessionBridge: bridge }), null)
})

test('T03: user-info rejects query token; QR client adopts a local session without SSO cookies', () => {
  const index = readFileSync(join(root, 'lib/index.js'), 'utf8')
  const client = readFileSync(join(root, 'lib/client.js'), 'utf8')
  assert.match(index, /token_in_query_forbidden/)
  assert.ok(client.includes('adoptAuthSession(auth)'))
  assert.ok(!client.includes("setCookie('PORTALSSOCookie', token"))
  assert.doesNotMatch(client, /user-info\?empNo=/)
})
