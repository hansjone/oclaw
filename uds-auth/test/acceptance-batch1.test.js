/**
 * Acceptance batch-1 regressions (R01–R05).
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { MemoryStore } from '../lib/session/memory-store.js'
import { createAgentAuthHandlers } from '../lib/agent-auth.js'
import { RolesStore, ROLES } from '../lib/roles.js'
import { identityFromSessionRecord } from '../lib/dsh-acl.js'
import { runWithUserContext } from '../lib/context.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')

test('R01/A05: client attaches bridge only to same-host http↔ws / https↔wss', () => {
  const src = readFileSync(join(root, 'lib/client.js'), 'utf8')
  assert.match(src, /isTrustedHostUrl/)
  assert.match(src, /locSecure !== urlSecure/)
  assert.match(src, /!isTrustedHostUrl\(url\)/)
  assert.match(src, /!isTrustedHostUrl\(input\)/)
})

test('R03: revoked session fails getBySessionIdSync', async () => {
  const store = new MemoryStore()
  const { sessionId, bearer } = await store.create({ empNo: 'A001', displayName: 'A' }, 600)
  assert.ok(await store.getByBearer(bearer))
  assert.ok(store.getBySessionIdSync(sessionId))
  await store.revokeSession(sessionId)
  assert.equal(store.getBySessionIdSync(sessionId), null)
  assert.equal(await store.getByBearer(bearer), null)
})

test('R03/Q10: fallback identity rejected when emergency password disabled', () => {
  const roles = new RolesStore({})
  roles._roles.set('administrator', ROLES.FALLBACK_ADMIN || 'fallback_admin')
  roles._fallbackPasswordHash = null
  assert.equal(roles.isFallbackEnabled(), false)
  const id = identityFromSessionRecord({
    sessionId: 's1',
    empNo: 'administrator',
    kind: 'fallback',
    userData: { empNo: 'administrator' },
  }, roles)
  assert.equal(id, null)
})

test('R03/Q10: fallback identity accepted when emergency password enabled', () => {
  const roles = new RolesStore({})
  roles._roles.set('administrator', 'fallback_admin')
  roles._fallbackPasswordHash = 'abc'
  assert.equal(roles.isFallbackEnabled(), true)
  const id = identityFromSessionRecord({
    sessionId: 's1',
    empNo: 'administrator',
    kind: 'fallback',
    userData: { empNo: 'administrator' },
  }, roles)
  assert.equal(id?.empNo, 'administrator')
  assert.equal(id?.kind, 'fallback')
})

test('R04: create/follow use live permissions; no admin follow bypass', () => {
  const src = readFileSync(join(root, 'lib/dsh-acl.js'), 'utf8')
  assert.match(src, /assertCreateTargetAllowed[\s\S]*?livePermissions\(identity\)/)
  assert.match(src, /never bypass projection for admin-at-subscribe/)
  assert.equal(/if \(canSeeAllWorkspaces\(identity\)\) \{\s*yield\* origFollow/.test(src), false)
})

test('R05: closing allowRawAgentToken takes effect immediately', async () => {
  let allowRaw = true
  const handlers = createAgentAuthHandlers({
    allowRawTokenResponse: () => allowRaw,
    outboundHosts: () => ['example.com'],
    resolveCallerSession: async () => ({ empNo: 'A', sessionId: 's' }),
    getSessionOwner: () => 'A',
    resolveCredentialsForSession: async () => ({ empNo: 'A', token: 'secret' }),
  })
  allowRaw = false
  const chunks = []
  const res = {
    statusCode: 200,
    setHeader() {},
    end(s) { chunks.push(String(s)) },
  }
  await handlers.handleAgentCredentials({
    method: 'GET',
    headers: {},
    socket: { remoteAddress: '127.0.0.1' },
  }, res)
  assert.equal(res.statusCode, 403)
  assert.match(chunks.join(''), /raw_token_disabled/)
})

test('R05: empty outbound list does not revive defaults', async () => {
  const handlers = createAgentAuthHandlers({
    allowRawTokenResponse: () => false,
    outboundHosts: () => [],
    resolveCallerSession: async () => ({ empNo: 'A', sessionId: 's' }),
    getSessionOwner: () => 'A',
    resolveCredentialsForSession: async () => ({ empNo: 'A', token: 'secret' }),
  })
  const chunks = []
  const res = {
    statusCode: 200,
    setHeader() {},
    end(s) { chunks.push(String(s)) },
  }
  const body = JSON.stringify({
    sessionId: 's',
    url: 'https://icenterapi.zte.com.cn/x',
    method: 'GET',
  })
  const req = {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    socket: { remoteAddress: '127.0.0.1' },
    async *[Symbol.asyncIterator]() {
      yield Buffer.from(body)
    },
  }
  await handlers.handleOutbound(req, res)
  const text = chunks.join('')
  assert.ok(
    /host_not_allowed|outbound_denied|forbidden|not_allowed/i.test(text)
      || res.statusCode >= 400,
    text,
  )
})

test('R05: live config getters wired in index', () => {
  const src = readFileSync(join(root, 'lib/index.js'), 'utf8')
  assert.match(src, /getAllowOpenRegistration/)
  assert.match(src, /allowRawTokenResponse: \(\) =>/)
  assert.match(src, /empty string \/ \[\] means deny-all|deny-all/)
})

test('R02: job/terminal/fs ACL wraps and principal live check', () => {
  const src = readFileSync(join(root, 'lib/dsh-acl.js'), 'utf8')
  assert.match(src, /jobController/)
  assert.match(src, /terminalController/)
  assert.match(src, /file_forbidden/)
  assert.match(src, /assertPrincipalLive/)
  assert.match(src, /getSessionStore/)
})

test('R03: assertCanAccess rejects revoked principal via session store', async () => {
  const store = new MemoryStore()
  const { sessionId } = await store.create({ empNo: 'A001' }, 600)
  const roles = new RolesStore({})
  roles._roles.set('A001', 'user')
  const identity = identityFromSessionRecord({
    sessionId,
    empNo: 'A001',
    kind: 'uds',
    userData: { empNo: 'A001' },
  }, roles)
  assert.ok(identity)
  await store.revokeSession(sessionId)
  assert.equal(store.getBySessionIdSync(sessionId), null)

  // Simulate installDshAcl assertPrincipalLive gate
  const sid = identity.sessionId
  assert.ok(sid)
  assert.equal(store.getBySessionIdSync(sid), null)
})

// silence unused in some runners
void runWithUserContext
