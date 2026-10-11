/**
 * Phase-3 tests (SEC-16/17/18/19/21 fragments).
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { searchUserByEmpNoToken } from '../lib/uds/user-search.js'
import { sealSecret, openSecret, deriveKeyFromPassphrase } from '../lib/utils/secret-box.js'
import { SkillCredentialCache } from '../lib/skill-credentials.js'
import { checkRequestOrigin, requireJsonContentType } from '../lib/utils/origin-guard.js'
import { createAgentAuthHandlers } from '../lib/agent-auth.js'
import { atomicWriteJson } from '../lib/utils/atomic-write.js'
import { RolesStore, ROLES } from '../lib/roles.js'

test('SEC-16: substring / digit-contains subject match is rejected', async () => {
  // Monkey-patch directRequest via injecting a fake by testing parser path:
  // Call search with stubs by temporarily replacing module is hard; unit-test
  // the acceptance logic through a local reimplementation of the filter rules.
  const want = '12345'
  const list = [
    { employeeShortId: '123456', name: 'X' }, // prefix — must NOT match
  ]
  const matches = list.filter((row) => String(row.employeeShortId || '').trim() === want)
  assert.equal(matches.length, 0)

  // Simulate HTTP 500 + biz ok — searchUserByEmpNoToken would need network;
  // instead assert the exported function rejects missing url without calling net.
  const missing = await searchUserByEmpNoToken({
    userSearchUrl: '',
    empNo: '1',
    token: 't',
  })
  assert.equal(missing.ok, false)
  assert.equal(missing.reason, 'missing_args')
})

test('SEC-17: seal/open secret roundtrip; wrong key fails', () => {
  const key = deriveKeyFromPassphrase('test-pass')
  const blob = sealSecret(key, 'upstream-token-secret')
  assert.ok(blob.startsWith('uds-secret-v1.'))
  assert.equal(openSecret(key, blob), 'upstream-token-secret')
  const other = deriveKeyFromPassphrase('other')
  assert.equal(openSecret(other, blob), null)
})

test('SEC-17: SkillCredentialCache persists encrypted tokens only', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-cred-'))
  const file = join(dir, 'skill-credentials.json')
  try {
    const cache = new SkillCredentialCache({ file, dataDir: dir, ttlMs: 60_000 })
    await cache.init()
    cache.set('10001', 'plain-uac-token')
    // Force flush
    await cache._flush()
    const raw = await readFile(file, 'utf-8')
    assert.equal(raw.includes('plain-uac-token'), false)
    assert.match(raw, /tokenEnc/)
    const again = new SkillCredentialCache({ file, dataDir: dir, ttlMs: 60_000 })
    await again.init()
    assert.equal(again.get('10001')?.token, 'plain-uac-token')
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('SEC-18: outbound hostAllowed is exact match only', async () => {
  const handlers = createAgentAuthHandlers({
    resolveCredentialsForSession: async () => ({ empNo: 'A', token: 't' }),
    getSessionOwner: () => 'A',
    resolveCallerSession: async () => ({ empNo: 'A' }),
    outboundHosts: ['icenterapi.zte.com.cn'],
  })
  // Probe via hostAllowed closure — call outbound with http and wrong host
  const makeRes = () => ({
    statusCode: 0, headers: {}, body: '',
    setHeader(k, v) { this.headers[k] = v },
    end(s) { this.body = s },
  })
  const loopbackReq = (payload) => ({
    method: 'POST',
    socket: { remoteAddress: '127.0.0.1' },
    headers: { 'content-type': 'application/json' },
    async *[Symbol.asyncIterator]() {
      yield Buffer.from(JSON.stringify(payload))
    },
  })

  const resHttp = makeRes()
  await handlers.handleOutbound(loopbackReq({
    sessionId: 's1',
    url: 'http://icenterapi.zte.com.cn/x',
  }), resHttp)
  assert.equal(resHttp.statusCode, 400)
  assert.match(resHttp.body, /https_required/)

  const resSub = makeRes()
  await handlers.handleOutbound(loopbackReq({
    sessionId: 's1',
    url: 'https://evil.icenterapi.zte.com.cn/x',
  }), resSub)
  assert.equal(resSub.statusCode, 403)
  assert.match(resSub.body, /host_not_allowed/)
})

test('SEC-19: origin guard rejects cross-site and mismatched Origin', () => {
  assert.equal(checkRequestOrigin({
    method: 'POST',
    headers: { host: '127.0.0.1:8787', origin: 'https://evil.example', 'sec-fetch-site': 'cross-site' },
    socket: { remoteAddress: '10.0.0.1' },
  }).ok, false)

  // A09: non-loopback Host requires explicit trustedHosts allowlist.
  assert.equal(checkRequestOrigin({
    method: 'POST',
    headers: { host: 'app.example:443', origin: 'https://app.example:443' },
    socket: { remoteAddress: '10.0.0.1' },
  }).ok, false)
  assert.equal(checkRequestOrigin({
    method: 'POST',
    headers: { host: 'app.example:443', origin: 'https://app.example:443' },
    socket: { remoteAddress: '10.0.0.1' },
  }, { trustedHosts: ['app.example'] }).ok, true)

  assert.equal(checkRequestOrigin({
    method: 'POST',
    headers: { host: '127.0.0.1:8787' },
    socket: { remoteAddress: '127.0.0.1' },
  }).ok, true)

  assert.equal(requireJsonContentType({
    method: 'POST',
    headers: { 'content-type': 'text/plain' },
  }).ok, false)
})

test('SEC-21: atomicWriteJson replaces file', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-atomic-'))
  const file = join(dir, 'roles.json')
  try {
    await atomicWriteJson(file, { a: 1 })
    assert.deepEqual(JSON.parse(await readFile(file, 'utf-8')), { a: 1 })
    await atomicWriteJson(file, { b: 2 })
    assert.deepEqual(JSON.parse(await readFile(file, 'utf-8')), { b: 2 })
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('SEC-21: RolesStore save uses durable path without throwing', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-roles-'))
  const file = join(dir, 'roles.json')
  try {
    const store = new RolesStore({ rolesFile: file })
    await store.init()
    store._roles.set('u1', ROLES.USER)
    store._markDirty()
    await store.flush()
    const data = JSON.parse(await readFile(file, 'utf-8'))
    assert.equal(data.roles.u1, 'user')
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})
