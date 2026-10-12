import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile, mkdir, rm, readdir, lstat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { RolesStore, ROLES } from '../lib/roles.js'
import { hashPasswordAsync, derivePasswordKey } from '../lib/utils/password-kdf.js'
import { sealLocalAdminBox, openLocalAdminBoxAsync } from '../lib/local-admin.js'
import { QrChallengeStore, qrLoginCredentials } from '../lib/qr-challenge.js'
import { TaskCapabilityStore } from '../lib/task-capability.js'
import { createTaskEnvironment } from '../lib/task-environment.js'
import { SessionBridgeStore } from '../lib/session-bridge.js'
import { extractSessionBearer } from '../lib/session/request-auth.js'
import { migrateState } from '../lib/state-migration.js'
import { atomicWriteFile } from '../lib/utils/atomic-write.js'
import { checkRequestOrigin } from '../lib/utils/origin-guard.js'
import { protectProfileDirectory } from '../lib/profile-security.js'
import { runInNewContext } from 'node:vm'
import { installGatewayPolicy } from '../lib/gateway-policy.js'
import { installGatewayEvents } from '../lib/gateway-events.js'

test('Gateway guards new namespaces and lookup owners before invocation, including live streams', async () => {
  let principal = { empNo: 'u' }, active = true, viewAll = false, prepared = 0
  const descriptors = {
    global: { namespace: 'newPlugin', method: 'global', parameters: [], invocation: { kind: 'direct' } },
    read: { namespace: 'newPlugin', method: 'read', parameters: [{ name: 'workspaceFileScope', source: 'lookup', wire: 'workspaceFileScopeId' }], invocation: { kind: 'direct' } },
    stream: { namespace: 'newPlugin', method: 'stream', parameters: [{ name: 'sessionId', wire: 'sessionId' }], invocation: { kind: 'direct' }, mode: 'stream' },
  }
  const gateway = {
    async *openRemoteEvents() {}, receiveRemoteEventResult() {},
    resolveDescriptor(ns, method) { return descriptors[method] },
    async prepareInvocation(request) {
      prepared++
      return { method: request.method === 'stream' ? async function* () { yield 'first'; yield 'second' } : () => 'ok' }
    },
  }
  installGatewayPolicy(gateway, { identity: () => principal,
    assertPrincipal: p => { if (!p || !active) throw new Error('login_required') },
    permissions: () => ({ canAccessSettings: viewAll }),
    assertSession: sid => { if (sid !== 'own') throw new Error('session_forbidden') },
    deny: code => { throw new Error(code) } })
  await assert.rejects(gateway.prepareInvocation({ namespace: 'newPlugin', method: 'global', args: {} }), /forbidden_settings/)
  await assert.rejects(gateway.prepareInvocation({ namespace: 'newPlugin', method: 'read', args: { workspaceFileScopeId: 'foreign' } }), /session_forbidden/)
  assert.equal(prepared, 0, 'authorization precedes providers and lookups')
  const invocation = await gateway.prepareInvocation({ namespace: 'newPlugin', method: 'read', args: { workspaceFileScopeId: 'own' } })
  assert.equal(invocation.method(), 'ok')
  const stream = (await gateway.prepareInvocation({ namespace: 'newPlugin', method: 'stream', args: { sessionId: 'own' } })).method()
  assert.equal((await stream.next()).value, 'first')
  active = false; await assert.rejects(stream.next(), /login_required/)
  principal = undefined
  assert.equal((await gateway.prepareInvocation({ namespace: 'newPlugin', method: 'global', args: {} })).method(), 'ok')
  principal = null; await assert.rejects(gateway.prepareInvocation({ namespace: 'newPlugin', method: 'global', args: {} }), /login_required/)
  assert.throws(() => installGatewayPolicy({}, {}), /unsupported_gateway_acl_contract/)
})

test('Gateway event stream hides foreign events and binds responses to the issuing local session', async () => {
  let principal = { empNo: 'u', sessionId: 'login1' }, active = true
  let finish
  const gate = new Promise(resolve => { finish = resolve })
  const gateway = { pendingRemoteEvents: new Map([['event-own', { frame: { agentId: 'own' } }]]),
    async *openRemoteEvents() {
      yield { type: 'ready', clientId: 'client1', host: { home: 'private-home' } }
      yield { type: 'emit', event: 'api-session/added', args: [{ id: 'foreign', title: 'secret' }] }
      yield { type: 'emit', event: 'api-session/status', args: ['own', true] }
      yield { type: 'emit', event: 'credentials/record-updated', args: ['global-secret'] }
      yield { type: 'waterfall', eventId: 'event-foreign', agentId: 'foreign', request: { secret: 'hidden' } }
      yield { type: 'waterfall', eventId: 'event-own', agentId: 'own', request: {} }
      await gate
      yield { type: 'emit', event: 'api-session/status', args: ['own', false] }
    }, receiveRemoteEventResult() { return 'accepted' } }
  installGatewayEvents(gateway, { identity: () => principal,
    assertPrincipal: p => { if (!p || !active) throw new Error('login_required') },
    permissions: () => ({ canAccessSettings: false }), assertSession: sid => { if (sid !== 'own') throw new Error('session_forbidden') },
    deny: code => { throw new Error(code) } })
  const stream = gateway.openRemoteEvents()
  assert.deepEqual((await stream.next()).value.host, { home: '' })
  assert.equal((await stream.next()).value.event, 'api-session/status')
  assert.equal((await stream.next()).value.eventId, 'event-own')
  const result = { clientId: 'client1', eventId: 'event-own' }
  assert.equal(gateway.receiveRemoteEventResult({}, result), 'accepted')
  principal = { empNo: 'u', sessionId: 'login2' }
  assert.throws(() => gateway.receiveRemoteEventResult({}, result), /event_client_forbidden/)
  active = false; finish(); await assert.rejects(stream.next(), /login_required/)
})

test('background shell capability survives foreground completion and ends with its own job', () => {
  const caps = new TaskCapabilityStore(), roles = new RolesStore({}), controller = new AbortController()
  const env = createTaskEnvironment({ getOwner: () => 'u', rolesStore: roles, capabilities: caps, getWebServer: () => ({ port: 12345 }) })
  const execution = { token: {}, agent: { session: { header: { id: 'own' } } }, signal: controller.signal }
  const values = env.contributor.resolve(execution)
  let listener, unsubscribed = false
  const jobs = { list: () => [{ id: 'job1', status: 'running' }], events: { subscribe(scope, fn) { assert.deepEqual(scope, { owner: 'own' }); listener = fn; return () => { unsubscribed = true } } } }
  env.finish(execution, { value: { kind: 'background', jobId: 'job1' } }, jobs)
  controller.abort()
  assert.ok(caps.verify(values.DSH_UDS_TASK_CAPABILITY))
  listener({ type: 'settled', job: { id: 'other' } }); assert.ok(caps.verify(values.DSH_UDS_TASK_CAPABILITY))
  listener({ type: 'settled', job: { id: 'job1' } }); assert.equal(caps.verify(values.DSH_UDS_TASK_CAPABILITY), null)
  assert.equal(unsubscribed, true)
})

async function temporary(t) {
  const dir = await mkdtemp(join(tmpdir(), 'uds-auth-0310-'))
  t.after(() => rm(dir, { recursive: true, force: true }))
  return dir
}

test('password transactions queue set/set/clear and persist a restart-safe generation', async t => {
  const dir = await temporary(t), file = join(dir, 'roles.json')
  const store = new RolesStore({ rolesFile: file })
  await store.init()
  // init() seeds the default emergency password, so assert relative to that baseline.
  const base = store.getFallbackCredVersion()
  await Promise.all([
    store.setFallbackPassword('password-first-0310', ROLES.SUPER_ADMIN),
    store.setFallbackPassword('password-second-0310', ROLES.SUPER_ADMIN),
    store.clearFallbackPassword(ROLES.SUPER_ADMIN),
  ])
  assert.equal(store.isFallbackEnabled(), false)
  assert.equal(store.getFallbackCredVersion(), base + 3)
  const reopened = new RolesStore({ rolesFile: file }); await reopened.init()
  assert.equal(reopened.isFallbackEnabled(), false)
  assert.equal(reopened.getFallbackCredVersion(), base + 3)
})

test('queued admin writes recheck the actor after a preceding demotion commits', async t => {
  const store = new RolesStore({ rolesFile: join(await temporary(t), 'roles.json') }); await store.init()
  await store.ensureUser('actor', ROLES.SUPER_ADMIN); await store.setRole('actor', ROLES.ADMIN, ROLES.SUPER_ADMIN)
  await store.ensureUser('target', ROLES.SUPER_ADMIN)
  const flush = store.flush.bind(store)
  let start, finish
  const started = new Promise(resolve => { start = resolve }), gate = new Promise(resolve => { finish = resolve })
  store.flush = async () => { start(); await gate; return flush() }
  const demotion = store.setRole('actor', ROLES.USER, ROLES.SUPER_ADMIN)
  await started
  const stale = store.setRole('target', ROLES.ADMIN, () => store.getRole('actor'))
  const denied = assert.rejects(stale, { code: 'forbidden_set_role' })
  finish(); await demotion; await denied
  assert.equal(store.getRole('target'), ROLES.USER)
})

test('failed credential write cannot resurrect an uncommitted peer; next queued write commits', async t => {
  const file = join(await temporary(t), 'roles.json')
  const store = new RolesStore({ rolesFile: file }); await store.init()
  await store.setFallbackPassword('original-password-0310', ROLES.SUPER_ADMIN)
  const durable = store.getFallbackCredVersion()
  const originalFlush = store.flush.bind(store)
  let start, finish
  const started = new Promise(r => start = r), gate = new Promise(r => finish = r)
  let count = 0
  store.flush = async () => {
    if (++count === 1) { start(); await gate; throw new Error('injected-write-failure') }
    await originalFlush()
  }
  const first = store.setFallbackPassword('uncommitted-password-0310', ROLES.SUPER_ADMIN)
  const failure = assert.rejects(first, /injected-write-failure/)
  await started
  const second = store.setFallbackPassword('committed-second-0310', ROLES.SUPER_ADMIN)
  assert.equal(store.getFallbackCredVersion(), durable, 'readers see only the durable generation')
  finish(); await failure; await second
  assert.equal(await store.verifyFallbackAsync('uncommitted-password-0310', 'ip1'), false)
  assert.equal(await store.verifyFallbackAsync('committed-second-0310', 'ip2'), true)
  const again = new RolesStore({ rolesFile: file }); await again.init()
  assert.equal(again.getFallbackCredVersion(), durable + 1)
  assert.equal(await again.verifyFallbackAsync('committed-second-0310', 'ip3'), true)
})

test('staged role promotion is invisible before commit; failed preferences restore durable state', async t => {
  const store = new RolesStore({ rolesFile: join(await temporary(t), 'roles.json') }); await store.init()
  await store.ensureUser('u', ROLES.SUPER_ADMIN); await store.ensureUser('boss', ROLES.SUPER_ADMIN)
  await store.setRole('boss', ROLES.SUPER_ADMIN, ROLES.SUPER_ADMIN)
  let start, finish
  const started = new Promise(r => start = r), gate = new Promise(r => finish = r)
  store.flush = async () => { start(); await gate; throw new Error('disk-offline') }
  const promotion = store.setRole('u', ROLES.ADMIN, ROLES.SUPER_ADMIN)
  const failed = assert.rejects(promotion, /disk-offline/)
  await started
  assert.equal(store.resolvePermissions('u').canAccessSettings, false)
  finish(); await failed
  assert.equal(store.getRole('u'), ROLES.USER)
  await assert.rejects(store.setViewAllSessionsDurable('boss', false), /disk-offline/)
  assert.equal(store.resolvePermissions('boss').canViewAllSessions, true)
})

test('runtime KDF leaves the event loop responsive and rejects queue overload', async () => {
  let heartbeat = false
  const timer = setTimeout(() => { heartbeat = true }, 0)
  await hashPasswordAsync('responsive-password-0310')
  clearTimeout(timer)
  assert.equal(heartbeat, true)
  const results = await Promise.allSettled(Array.from({ length: 12 }, () => derivePasswordKey('load-password', Buffer.alloc(16))))
  assert.equal(results.filter(r => r.status === 'fulfilled').length, 10)
  assert.equal(results.filter(r => r.status === 'rejected' && r.reason.code === 'kdf_busy').length, 2)
})

test('async sealed-box unlock uses the existing wire format and rejects wrong passphrase', async () => {
  const box = sealLocalAdminBox('offline-passphrase-0310')
  assert.equal((await openLocalAdminBoxAsync(box, 'offline-passphrase-0310')).ok, true)
  assert.equal((await openLocalAdminBoxAsync(box, 'wrong-passphrase-0310')).ok, false)
})

test('QR pending survives; public scan coordinates cannot poll or consume on another browser', () => {
  const store = new QrChallengeStore(), c = store.create({ loginSystemCode: 'sys', originSystemCode: '' })
  assert.equal(c.qrCodeStr.includes(c.browserBinding), false)
  assert.equal(store.peek(c.qrCodeKey, c.qrCodeValue, '').reason, 'qr_binding_required')
  assert.equal(store.peek(c.qrCodeKey, c.qrCodeValue, 'f'.repeat(64)).ok, false)
  assert.equal(store.peek(c.qrCodeKey, c.qrCodeValue, c.browserBinding).ok, true)
  assert.equal(store.peek(c.qrCodeKey, c.qrCodeValue, c.browserBinding).ok, true)
  const results = Array.from({ length: 20 }, () => store.consume(c.qrCodeKey, c.qrCodeValue, c.browserBinding))
  assert.equal(results.filter(r => r.ok).length, 1)
  assert.equal(results.filter(r => r.reason === 'qr_replay').length, 19)
})

test('QR expiry and missing-credential success fail closed', () => {
  const store = new QrChallengeStore(), c = store.create({ loginSystemCode: 'sys', originSystemCode: '' })
  store.rows.get(c.qrCodeKey).expiresAt = Date.now() - 1
  assert.equal(store.consume(c.qrCodeKey, c.qrCodeValue, c.browserBinding).reason, 'qr_expired')
  assert.equal(qrLoginCredentials({ code: { code: '0000' }, bo: { code: '0000' } }), null)
  assert.equal(qrLoginCredentials({ code: '0000', bo: { code: '4002' }, other: { account: 'u', token: 't' } }), null)
  assert.deepEqual(qrLoginCredentials({ code: '0000', bo: { code: '0000' }, other: { account: 'u', token: 't' } }), { empNo: 'u', token: 't' })
})

test('shell/cron environment derives the owner and revokes on tool result/abort/disposal', () => {
  const roles = new RolesStore({}), caps = new TaskCapabilityStore()
  const owners = new Map([['s1', 'u']])
  const env = createTaskEnvironment({ getOwner: sid => owners.get(sid), rolesStore: roles,
    capabilities: caps, getWebServer: () => ({ port: 43210 }) })
  const controller = new AbortController()
  const execution = { token: {}, agent: { session: { header: { id: 's1' } } }, signal: controller.signal,
    arguments: { empNo: 'other', env: { UDS_TASK_CAPABILITY: 'forged' } } }
  let values = env.contributor.resolve(execution)
  let cap = caps.verify(values.DSH_UDS_TASK_CAPABILITY, { dshSessionId: 's1' })
  assert.equal(cap.empNo, 'u'); assert.deepEqual(cap.scopes, ['outbound'])
  assert.equal(values.DSH_UDS_AUTH_BASE, 'http://127.0.0.1:43210/uds-auth')
  assert.equal(caps.verify(values.DSH_UDS_TASK_CAPABILITY, { dshSessionId: 's2' }), null)
  env.release({ token: execution.token }); assert.equal(caps.verify(values.DSH_UDS_TASK_CAPABILITY), null)
  values = env.contributor.resolve(execution); controller.abort()
  assert.equal(caps.verify(values.DSH_UDS_TASK_CAPABILITY), null)
  const next = { token: {}, agent: execution.agent, signal: new AbortController().signal }
  values = env.contributor.resolve(next); env.dispose()
  assert.equal(caps.verify(values.DSH_UDS_TASK_CAPABILITY), null)
  assert.equal(env.contributor.resolve({ token: {}, agent: { session: { header: { id: 'missing' } } } }).DSH_UDS_TASK_CAPABILITY, '')
})

test('WS tickets authorize only GET with a real upgrade on the Gateway mux entry', () => {
  const bridge = new SessionBridgeStore({}), cap = bridge.mintWsTicket({ empNo: 'u', bearer: 'b'.repeat(32) })
  const headers = { upgrade: 'websocket', connection: 'Upgrade' }
  const good = { method: 'GET', url: '/api/remote.mux?udsWsTicket=' + cap.ticket, headers }
  // Wrong path / method must not consume. Missing Connection is allowed (0.3.9 Desktop).
  for (const bad of [
    { ...good, url: '/foreign?udsWsTicket=' + cap.ticket },
    { ...good, method: 'POST' },
    { ...good, headers: { connection: 'Upgrade' } },
  ]) {
    assert.equal(extractSessionBearer(bad, { sessionBridge: bridge }), null)
  }
  assert.equal(
    extractSessionBearer(
      { ...good, headers: { upgrade: 'websocket' } },
      { sessionBridge: bridge },
    )?.via,
    'ws_ticket',
  )
  const cap2 = bridge.mintWsTicket({ empNo: 'u', bearer: 'b'.repeat(32) })
  const good2 = { method: 'GET', url: '/api/remote.mux?udsWsTicket=' + cap2.ticket, headers }
  assert.equal(extractSessionBearer(good2, { sessionBridge: bridge })?.via, 'ws_ticket')
  assert.equal(extractSessionBearer(good2, { sessionBridge: bridge }), null)
})

test('Host/CSRF/upgrade matrix rejects hostile authority, Origin and browser cross-site signals', () => {
  const req = { method: 'POST', headers: { host: 'localhost:3000', origin: 'http://localhost:3000' }, socket: { remoteAddress: '127.0.0.1' } }
  assert.equal(checkRequestOrigin(req).ok, true)
  for (const headers of [{ ...req.headers, host: 'evil.invalid:3000' }, { ...req.headers, origin: 'http://evil.invalid:3000' },
    { ...req.headers, origin: 'file://localhost:3000' }, { ...req.headers, origin: 'http://localhost:3000/path' },
    { ...req.headers, host: 'localhost:3000/evil' }, { ...req.headers, 'sec-fetch-site': 'cross-site' }]) {
    assert.equal(checkRequestOrigin({ ...req, method: 'GET', headers }, { upgrade: true }).ok, false)
  }
  assert.equal(checkRequestOrigin({ ...req, headers: { host: '[::1]:3000', origin: 'null' }, socket: { remoteAddress: '::1' } }).ok, true)
  assert.equal(checkRequestOrigin({ ...req, headers: { host: 'localhost:3000', origin: 'dsh-app://app' } }).ok, true)
  assert.equal(checkRequestOrigin({ ...req, headers: { host: 'localhost:3000', origin: 'dsh-app://foreign' } }).ok, false)
})

test('legacy migration rolls back partial writes, resumes identical files and never overwrites conflicts', async t => {
  const root = await temporary(t), src = join(root, 'src'), dst = join(root, 'dst')
  await mkdir(src); await mkdir(dst)
  await writeFile(join(src, 'roles.json'), '{"roles":{"boss":"super_admin"}}')
  await writeFile(join(src, 'session-owners.json'), '{"owners":{"s":"boss"}}')
  let calls = 0
  const { copyFile } = await import('node:fs/promises')
  await assert.rejects(migrateState(dst, src, { error() {} }, { copyFile: async (...args) => {
    if (++calls === 2) throw Object.assign(new Error('disk error'), { code: 'EIO' })
    return copyFile(...args)
  } }), /disk error/)
  assert.deepEqual(await readdir(dst), [])
  await copyFile(join(src, 'roles.json'), join(dst, 'roles.json'))
  assert.equal((await migrateState(dst, src, { info() {} })).migrated, true)
  assert.equal((await migrateState(dst, src)).reason, 'already')
  const conflict = join(root, 'conflict'); await mkdir(conflict)
  await writeFile(join(conflict, 'roles.json'), '{"roles":{}}')
  await assert.rejects(migrateState(conflict, src), { code: 'legacy_migrate_conflict' })
  assert.deepEqual(await readdir(conflict), ['roles.json'])
})

test('failed atomic rename cleans temporary secret buffers from disk', async t => {
  const dir = await temporary(t), dest = join(dir, 'directory'); await mkdir(dest)
  await assert.rejects(atomicWriteFile(dest, 'secret'))
  assert.deepEqual(await readdir(dir), ['directory'])
})

test('profile applies and verifies actual platform permissions on a disposable directory', async t => {
  const dir = await temporary(t); await writeFile(join(dir, 'roles.json'), '{}')
  const result = await protectProfileDirectory(dir)
  if (process.platform === 'win32') {
    assert.equal(result.protected, true); assert.deepEqual(result.principals, ['current-user', 'SYSTEM'])
  } else {
    assert.equal((await lstat(dir)).mode & 0o777, 0o700)
    assert.equal((await lstat(join(dir, 'roles.json'))).mode & 0o777, 0o600)
  }
})

test('actual Desktop fetch/WS wrapper preserves headers and only attaches credentials to the owned authority', async () => {
  const src = await readFile(new URL('../lib/client.js', import.meta.url), 'utf8')
  const calls = [], sockets = [], bridge = { empNo: 'administrator', token: 'b'.repeat(32), kind: 'sealed_box' }
  const window = { fetch: async (input, opts) => { calls.push({ input, opts }); return {} },
    WebSocket: function(url) { sockets.push(url) }, localStorage: { getItem: () => JSON.stringify(bridge) },
    __ModuleLoader__: { load({ factory }) { factory(() => ({ createElement() {} })) } } }
  const location = { protocol: 'dsh-app:', hostname: 'app', port: '', href: 'dsh-app://app/' }
  const ticketOpens = []
  const context = { window, location, URL, Headers, console, XMLHttpRequest: function() {
    this.open = (method, url) => { ticketOpens.push(String(url)) }
    this.setRequestHeader = () => {}; this.send = () => {}
    this.status = 200; this.responseText = '{"ticket":"once"}'
  } }
  runInNewContext(src, context)
  // 0.3.9: without streamBaseUrl, only loopback is trusted (not arbitrary hosts).
  await window.fetch('http://example.com/api/remote')
  assert.equal(calls.at(-1).opts, undefined, 'boot not ready must not trust non-loopback')
  await window.fetch('http://127.0.0.1:1111/api/remote')
  assert.equal(calls.at(-1).opts.headers['X-UDS-Bridge-Token'], bridge.token, 'loopback Gateway trusted before transport ready')
  context.__DSH_TRANSPORT__ = { streamBaseUrl: 'http://127.0.0.1:43210/' }
  await window.fetch('dsh-app://foreign/api/remote'); assert.equal(calls.at(-1).opts, undefined)
  await window.fetch('http://127.0.0.1:43211/api/remote'); assert.equal(calls.at(-1).opts, undefined)
  await window.fetch({ url: 'http://127.0.0.1:43210/api/remote', headers: new Headers({ 'X-Original': 'keep' }) })
  assert.equal(calls.at(-1).opts.headers['X-UDS-Bridge-Token'], bridge.token)
  assert.equal(calls.at(-1).opts.headers['x-original'], 'keep')
  assert.equal(calls.at(-1).opts.redirect, 'error')
  new window.WebSocket('ws://127.0.0.1:43210/api/remote.mux')
  assert.equal(new URL(sockets.at(-1)).searchParams.get('udsWsTicket'), 'once')
  assert.equal(sockets.at(-1).includes(bridge.token), false)
  assert.ok(
    ticketOpens[0] === '/uds-auth/api/ws-ticket'
      || ticketOpens.some((u) => u.startsWith('http://127.0.0.1:43210/uds-auth/api/ws-ticket')),
    'Desktop ticket mint must hit relative /uds-auth or Host streamBaseUrl',
  )
  new window.WebSocket('ws://127.0.0.1:43210/foreign')
  assert.equal(new URL(sockets.at(-1)).search, '')
})
