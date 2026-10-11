/**
 * Acceptance batch-2/3 regressions (R06–R14 fragments).
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { mkdtemp, writeFile, readFile, mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { TaskCapabilityStore } from '../lib/task-capability.js'
import { createAgentAuthHandlers } from '../lib/agent-auth.js'
import { RolesStore, ROLES, ACCOUNT_STATUS, LEGACY_DEFAULT_SHA256, hashPasswordScrypt, verifyPasswordHash } from '../lib/roles.js'
import { loadOrCreateSecretKey, sealSecret } from '../lib/utils/secret-box.js'
import { checkRequestOrigin } from '../lib/utils/origin-guard.js'
import { SessionAclStore } from '../lib/session-acl.js'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')

test('R06: task capability authorizes outbound without browser session', async () => {
  const caps = new TaskCapabilityStore({ defaultTtlSeconds: 600 })
  const minted = caps.mint({
    empNo: 'A001',
    dshSessionId: 'sess-a',
    scopes: ['outbound', 'credentials'],
  })
  const handlers = createAgentAuthHandlers({
    taskCapabilities: caps,
    allowRawTokenResponse: () => false,
    outboundHosts: () => ['example.com'],
    getSessionOwner: () => 'A001',
    resolveCredentialsForSession: async () => ({ empNo: 'A001', token: 'tok' }),
    resolveCallerSession: async () => null,
  })
  const chunks = []
  const res = { statusCode: 200, setHeader() {}, end(s) { chunks.push(String(s)) } }
  // credentials still blocked when raw disabled
  await handlers.handleAgentCredentials({
    method: 'POST',
    headers: {
      'x-uds-task-capability': minted.token,
      'x-dsh-session-id': 'sess-a',
      'content-type': 'application/json',
    },
    socket: { remoteAddress: '127.0.0.1' },
    async *[Symbol.asyncIterator]() {
      yield Buffer.from(JSON.stringify({ sessionId: 'sess-a', taskCapability: minted.token }))
    },
  }, res)
  assert.equal(res.statusCode, 403)
  assert.match(chunks.join(''), /raw_token_disabled/)

  // verify() binds empNo
  const v = caps.verify(minted.token, { audience: 'uds-auth-agent', dshSessionId: 'sess-a' })
  assert.equal(v?.empNo, 'A001')
  assert.equal(caps.verify('deadbeefdeadbeefdeadbeefdeadbeef', {}), null)
})

test('R07: user-info response includes bo whitelist (source)', () => {
  const src = readFileSync(join(root, 'lib/index.js'), 'utf8')
  assert.match(src, /bo: \[safeRow\]/)
  assert.match(src, /profile:\s*\{/)
})

test('R08: nested sessionIds and workspace remove projection (source)', () => {
  const src = readFileSync(join(root, 'lib/dsh-acl.js'), 'utf8')
  assert.match(src, /projectWorkspaceItem/)
  assert.match(src, /frame\.type === 'remove'/)
  assert.match(src, /projectMutationResult/)
})

test('R09: concurrent last-admin demotion keeps >=1 super_admin', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-roles-'))
  const file = join(dir, 'roles.json')
  const store = new RolesStore({ rolesFile: file })
  await store.init()
  store._roles.set('a', ROLES.SUPER_ADMIN)
  store._roles.set('b', ROLES.SUPER_ADMIN)
  store._dirty = true
  await store.flush()

  const results = await Promise.allSettled([
    store.setRole('a', ROLES.USER, ROLES.SUPER_ADMIN),
    store.setRole('b', ROLES.USER, ROLES.SUPER_ADMIN),
  ])
  const fulfilled = results.filter((r) => r.status === 'fulfilled').length
  const rejected = results.filter((r) => r.status === 'rejected').length
  assert.equal(fulfilled + rejected, 2)
  assert.ok(rejected >= 1, 'at least one demote must fail')
  const supers = await store.countByRole(ROLES.SUPER_ADMIN)
  assert.ok(supers >= 1, `remaining super_admins=${supers}`)
})

test('R09: corrupt session owners fail closed', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-own-'))
  const file = join(dir, 'owners.json')
  await writeFile(file, '{not-json', 'utf8')
  const store = new SessionAclStore({ ownersFile: file })
  await store.init()
  assert.equal(store.loadFailed, true)
})

test('R10: scrypt hash roundtrip; legacy default refused', () => {
  const h = hashPasswordScrypt('CorrectHorseBattery')
  assert.ok(h.startsWith('scrypt$'))
  assert.equal(verifyPasswordHash('CorrectHorseBattery', h), true)
  assert.equal(verifyPasswordHash('wrong', h), false)
  assert.equal(verifyPasswordHash('Admin@123', LEGACY_DEFAULT_SHA256), false)
})

test('R10: setFallbackPassword rejects short and known default', async () => {
  const store = new RolesStore({})
  store._roles.set('admin', ROLES.SUPER_ADMIN)
  await assert.rejects(() => store.setFallbackPassword('short', ROLES.SUPER_ADMIN), /password_too_short/)
  await assert.rejects(() => store.setFallbackPassword('Admin@123', ROLES.SUPER_ADMIN), /password_too_common/)
  await store.setFallbackPassword('LongEnoughPass1', ROLES.SUPER_ADMIN)
  assert.equal(store.verifyFallback('LongEnoughPass1', '127.0.0.1'), true)
})

test('R11: invalid env key fails closed', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-key-'))
  const prev = process.env.UDS_AUTH_SECRET_KEY
  process.env.UDS_AUTH_SECRET_KEY = 'not-hex'
  try {
    await assert.rejects(() => loadOrCreateSecretKey(dir), (err) => err.code === 'invalid_secret_key_env')
  } finally {
    if (prev === undefined) delete process.env.UDS_AUTH_SECRET_KEY
    else process.env.UDS_AUTH_SECRET_KEY = prev
  }
})

test('R11: corrupt key file is not replaced', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-key2-'))
  await writeFile(join(dir, '.uds-auth-secret-key'), 'garbage\n', 'utf8')
  const prev = process.env.UDS_AUTH_SECRET_KEY
  delete process.env.UDS_AUTH_SECRET_KEY
  try {
    await assert.rejects(() => loadOrCreateSecretKey(dir), (err) => err.code === 'secret_key_corrupt')
    const still = await readFile(join(dir, '.uds-auth-secret-key'), 'utf8')
    assert.match(still, /garbage/)
  } finally {
    if (prev !== undefined) process.env.UDS_AUTH_SECRET_KEY = prev
  }
})

test('R12: disabled account cannot be ensureUser / open-register revived', async () => {
  const store = new RolesStore({})
  store._roles.set('u1', ROLES.USER)
  store._roles.set('admin', ROLES.SUPER_ADMIN)
  await store.removeUser('u1', ROLES.SUPER_ADMIN)
  assert.equal(store.isDisabled('u1'), true)
  assert.equal(store.getAccountStatus('u1'), ACCOUNT_STATUS.DISABLED)
  await assert.rejects(() => store.ensureUser('u1', ROLES.SUPER_ADMIN), /account_disabled/)
})

test('R13: trustedHosts rejects unlisted Host', () => {
  const req = {
    method: 'POST',
    headers: {
      host: 'evil.example:8787',
      origin: 'https://evil.example:8787',
    },
    socket: { remoteAddress: '1.2.3.4' },
  }
  const denied = checkRequestOrigin(req, { trustedHosts: ['good.example:8787'] })
  assert.equal(denied.ok, false)
  assert.equal(denied.reason, 'host_not_trusted')
  const ok = checkRequestOrigin({
    method: 'POST',
    headers: { host: 'good.example:8787', origin: 'https://good.example:8787' },
    socket: { remoteAddress: '1.2.3.4' },
  }, { trustedHosts: ['good.example:8787'] })
  assert.equal(ok.ok, true)
})

test('R13/R14: QR challenge store + live identity patch + docs (source)', () => {
  const index = readFileSync(join(root, 'lib/index.js'), 'utf8')
  assert.match(index, /consumeQrChallenge/)
  assert.match(index, /MAX_QR_UPSTREAM_BYTES/)
  assert.match(index, /mintTaskCapability/)
  const acl = readFileSync(join(root, 'lib/dsh-acl.js'), 'utf8')
  assert.match(acl, /__udsAuthIdentityLive/)
  const readme = readFileSync(join(root, 'README.zh.md'), 'utf8')
  assert.doesNotMatch(readme, /Admin@123.*首次启动自动启用/)
  assert.match(readme, /mintTaskCapability|UDS_TASK_CAPABILITY/)
})

test('R06 python helper mentions task capability', () => {
  const py = readFileSync(join(root, 'skill-helpers/python/uds_skill_auth.py'), 'utf8')
  assert.match(py, /UDS_TASK_CAPABILITY/)
  assert.match(py, /X-UDS-Task-Capability/)
})
