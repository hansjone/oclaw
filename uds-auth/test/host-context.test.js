import assert from 'node:assert/strict'
import test from 'node:test'
import { getUserContext, runAsHost, withUserContext } from '../lib/context.js'
import { installDshAcl } from '../lib/dsh-acl.js'
import { MemoryStore } from '../lib/session/memory-store.js'

test('Host callback context is isolated across concurrent browser identities and exceptions', async () => {
  const identities = [null, { empNo: 'u1' }, { empNo: 'u2' }]
  await Promise.all(identities.map(identity => withUserContext(identity, async () => {
    assert.equal(await runAsHost(async () => {
      await Promise.resolve()
      assert.equal(getUserContext(), undefined)
      return 'host-result'
    }), 'host-result')
    assert.equal(getUserContext(), identity)
    assert.throws(() => runAsHost(() => { throw new Error('failed') }), /failed/)
    assert.equal(getUserContext(), identity)
  })))
  assert.equal(runAsHost(() => 42), 42)
  assert.throws(() => runAsHost(null), TypeError)
})

test('trusted Host creation works from browser ALS while unauthenticated browser creation stays denied', async () => {
  let creations = 0
  const owners = []
  const sessionStore = new MemoryStore()
  const minted = await sessionStore.create({ empNo: 'u1' }, 600)
  const controller = {
    async list() { return { items: [] } },
    async search() { return { items: [] } },
    async create(request) {
      creations += 1
      return { sessionId: `session-${creations}`, request }
    },
  }
  installDshAcl({
    on() { return () => {} },
    get() { return undefined },
    inject(names, callback) {
      if (names[0] === 'sessionController') callback({ sessionController: controller })
    },
  }, {
    sessionAcl: { getOwner() { return null }, setOwner: (...args) => owners.push(args) },
    userWorkspaces: { isUserPath: (empNo, path) => path === `/ws/${empNo}`, get() { return null } },
    getWorkspaceRoot: () => '/ws',
    getWorkspaceRegistry: () => undefined,
    getSessionStore: () => sessionStore,
  })
  await withUserContext(null, async () => {
    await assert.rejects(controller.create({ cwd: '/bot' }), error => (
      error.details.udsError === 'login_required_create_session'
    ))
    const result = await runAsHost(() => controller.create({ cwd: '/bot', agentPreset: 'netxops' }))
    assert.deepEqual(result.request, { cwd: '/bot', agentPreset: 'netxops' })
    assert.equal(getUserContext(), null)
    await assert.rejects(controller.create({ cwd: '/bot' }))
  })
  assert.equal(creations, 1)
  assert.deepEqual(owners, [], 'background sessions must not inherit a browser owner')
  await withUserContext({
    empNo: 'u1',
    sessionId: minted.sessionId,
    permissions: {},
  }, async () => {
    await assert.rejects(controller.create({ cwd: '/other' }), error => (
      error.details.udsError === 'session_workspace_only'
    ))
    await controller.create({ cwd: '/ws/u1' })
  })
  assert.deepEqual(owners, [['session-2', 'u1']])
})
