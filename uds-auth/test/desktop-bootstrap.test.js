import test from 'node:test'
import assert from 'node:assert/strict'
import { createDesktopBootstrap, DESKTOP_BOOTSTRAP_REF } from '../lib/desktop-bootstrap.js'
import { installGatewayPolicy } from '../lib/gateway-policy.js'

function fixture() {
  let configured = true, invoked = 0
  const services = {
    settings: { describe: () => [
      { ns: 'locale', value: { preference: 'zh', hidden: 'LOCALE-SECRET' } },
      { ns: 'llm-deepseek', value: { apiKeyEnv: 'REAL_KEY_NAME', endpoint: 'PRIVATE-ENDPOINT' } },
      { ns: 'uds-auth', value: { initialAdminEmpNo: 'PRIVATE-ADMIN' } },
    ] },
    llm: { listConfigurableProviders: () => [] },
    credentials: { describe: async ref => { assert.equal(ref, 'REAL_KEY_NAME'); return { configured, writable: true, value: 'RAW-KEY' } } },
    deepseekAccount: { getState: async () => ({ status: 'credential-stored', attempt: { authorizeUrl: 'SECRET-LOGIN-LINK' }, token: 'ACCOUNT-TOKEN' }) },
  }
  const deny = code => { throw new Error(code) }
  const project = createDesktopBootstrap({ getService: name => services[name], deny })
  let principal = null, admin = false, live = true
  const gateway = {
    async *openRemoteEvents() {}, receiveRemoteEventResult() {},
    resolveDescriptor: (namespace, method) => ({ namespace, method, parameters: [] }),
    prepareInvocation: async () => ({ method: () => { invoked++; return 'full-admin-result' } }),
  }
  installGatewayPolicy(gateway, { identity: () => principal, assertPrincipal: p => { if (!p || !live) deny('login_required') },
    assertSession: () => {}, permissions: () => ({ canAccessSettings: admin }), deny, desktopBootstrap: project })
  const invoke = async (namespace, method, args = {}) => (await gateway.prepareInvocation({ namespace, method, args })).method()
  return { invoke, services, setConfigured: value => { configured = value },
    setPrincipal: value => { principal = value }, setAdmin: value => { admin = value },
    revoke: () => { live = false }, invocations: () => invoked }
}

test('unmodified Desktop welcome reads a bounded projection before UDS login', async () => {
  const f = fixture()
  const settings = await f.invoke('settings', 'describe')
  assert.equal(settings.writable, false); assert.equal(settings.hasDocument, false)
  assert.equal(settings.namespaces.find(row => row.ns === 'locale').value.preference, 'zh')
  const providers = await f.invoke('llm', 'listConfigurableProviders')
  const refs = providers.map(provider => settings.namespaces.find(row => row.ns === provider.settingsNs).value.apiKeyEnv)
  const credentials = await f.invoke('credentials', 'describe', { refs })
  assert.deepEqual(credentials, { [DESKTOP_BOOTSTRAP_REF]: { configured: true, writable: false } })
  const account = await f.invoke('account', 'getState')
  assert.equal(account.status, 'credential-stored'); assert.equal(account.attempt, null)
  assert.equal(f.invocations(), 0, 'anonymous calls never invoke full Remote controllers')
  const data = JSON.stringify([settings, providers, credentials, account])
  for (const secret of ['REAL_KEY_NAME', 'PRIVATE-ENDPOINT', 'PRIVATE-ADMIN', 'RAW-KEY', 'ACCOUNT-TOKEN', 'SECRET-LOGIN-LINK', 'LOCALE-SECRET']) assert.equal(data.includes(secret), false)
  f.setConfigured(false)
  assert.equal((await f.invoke('credentials', 'describe', { refs }))[DESKTOP_BOOTSTRAP_REF].configured, false)
})

test('bootstrap cannot enumerate credential refs or access settings writes and sessions', async () => {
  const f = fixture()
  for (const args of [{ refs: ['REAL_KEY_NAME'] }, { refs: [DESKTOP_BOOTSTRAP_REF, 'OTHER'] }, {}, { refs: 'REAL_KEY_NAME' }]) {
    await assert.rejects(f.invoke('credentials', 'describe', args), /forbidden_settings/)
  }
  for (const [ns, method] of [['settings', 'update'], ['credentials', 'set'], ['account', 'startSignIn'], ['session', 'list'], ['newPlugin', 'describe']]) {
    await assert.rejects(f.invoke(ns, method), /login_required/)
  }
  assert.equal(f.invocations(), 0)
})

test('admin and trusted Host retain full reads; ordinary or revoked principals never receive them', async () => {
  const f = fixture()
  f.setPrincipal({ empNo: 'u' })
  assert.equal((await f.invoke('settings', 'describe')).writable, false)
  f.setAdmin(true)
  assert.equal(await f.invoke('settings', 'describe'), 'full-admin-result')
  f.setAdmin(false)
  assert.equal((await f.invoke('settings', 'describe')).writable, false)
  f.revoke()
  await assert.rejects(f.invoke('settings', 'describe'), /login_required/)
  f.setPrincipal(undefined)
  assert.equal(await f.invoke('settings', 'describe'), 'full-admin-result')
})

test('custom providers are detected without exposing their namespace or credential names', async () => {
  const f = fixture()
  f.services.settings.describe = () => [{ ns: 'private-provider', value: { profiles: { one: { apiKeyEnv: 'REAL_KEY_NAME' } } } }]
  f.services.llm.listConfigurableProviders = () => [{ settingsNs: 'private-provider', settingsPath: ['profiles', 'one'] }]
  const value = await f.invoke('credentials', 'describe', { refs: [DESKTOP_BOOTSTRAP_REF] })
  assert.equal(value[DESKTOP_BOOTSTRAP_REF].configured, true)
  assert.equal(JSON.stringify(await f.invoke('settings', 'describe')).includes('private-provider'), false)
})

test('projection still reports a stored key when another provider or reference throws', async () => {
  const deny = code => { throw new Error(code) }
  const services = {
    settings: { describe: () => [
      { ns: 'locale', value: {} },
      { ns: 'llm-deepseek', value: { apiKeyEnv: 'BROKEN_REF' } },
      { ns: 'llm-pi-ai', value: { providers: { suanlidao: { apiKeyEnv: 'SUANLIDAO_API_KEY' } } } },
    ] },
    llm: { listConfigurableProviders: () => [
      { provider: 'suanlidao', settingsNs: 'llm-pi-ai', settingsPath: ['providers', 'suanlidao'] },
    ] },
    credentials: { describe: async ref => {
      if (ref === 'BROKEN_REF') throw new Error('provider exploded')
      return { configured: ref === 'SUANLIDAO_API_KEY', writable: true }
    } },
    deepseekAccount: { getState: async () => { throw new Error('account backend down') } },
  }
  const project = createDesktopBootstrap({ getService: name => services[name], deny })
  const described = await project({ namespace: 'credentials', method: 'describe', args: { refs: [DESKTOP_BOOTSTRAP_REF] } })
  assert.equal(described[DESKTOP_BOOTSTRAP_REF].configured, true)
  const account = await project({ namespace: 'account', method: 'getState', args: {} })
  assert.equal(account.status, 'signed-out')
  services.settings.describe = () => { throw new Error('settings not mounted') }
  const none = await project({ namespace: 'credentials', method: 'describe', args: { refs: [DESKTOP_BOOTSTRAP_REF] } })
  assert.equal(none[DESKTOP_BOOTSTRAP_REF].configured, false)
})
