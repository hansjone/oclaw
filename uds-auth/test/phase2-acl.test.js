/**
 * Phase-2 ACL tests (SEC-10/12/13/14/15/26 fragments).
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { createSessionAccess } from '../lib/dsh-acl.js'
import { computePermissions, RolesStore, ROLES } from '../lib/roles.js'
import { SessionAclStore } from '../lib/session-acl.js'
import { UserWorkspaceStore, resolveWorkspaceRoot } from '../lib/workspace-provision.js'
import { sanitizeUserId, resolveUserDir } from '../lib/utils/safe-userid.js'
import { join } from 'node:path'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'

test('SEC-13: foreign owner is not overridden by own cwd', () => {
  const ownersMap = new Map([['s-foreign', 'u2']])
  const { canAccessSession } = createSessionAccess({
    sessionAcl: { getOwner: (id) => ownersMap.get(String(id)) || null },
    userWorkspaces: {
      get: (empNo) => (empNo === 'u1' ? { path: '/ws/u1', workspaceId: 'ws-u1' } : null),
      isUserPath: (empNo, candidate) => {
        if (empNo !== 'u1' || !candidate) return false
        const path = String(candidate).replace(/\\/g, '/')
        return path === '/ws/u1' || path.startsWith('/ws/u1/')
      },
    },
    getWorkspaceRoot: () => '/ws',
    getWorkspaceRegistry: () => ({ list: () => [] }),
  })
  const user = { empNo: 'u1', role: 'user', permissions: computePermissions('user') }
  assert.equal(canAccessSession('s-foreign', user, { cwd: '/ws/u1/project' }), false)
  assert.equal(canAccessSession('s-foreign', user, { cwd: '/ws/u2' }), false)
})

test('SEC-13: setOwner refuses overwrite of foreign owner without force', () => {
  const store = new SessionAclStore({})
  assert.equal(store.setOwner('s1', 'A'), true)
  assert.equal(store.setOwner('s1', 'B'), false)
  assert.equal(store.getOwner('s1'), 'A')
  assert.equal(store.setOwner('s1', 'B', { force: true }), true)
  assert.equal(store.getOwner('s1'), 'B')
})

test('SEC-14: sanitizeUserId rejects path escape segments', () => {
  assert.equal(sanitizeUserId('../escape'), null)
  assert.equal(sanitizeUserId('..\\escape'), null)
  assert.equal(sanitizeUserId('a/b'), null)
  assert.equal(sanitizeUserId('a\\b'), null)
  assert.equal(sanitizeUserId('C:'), null)
  assert.equal(sanitizeUserId('con'), null)
  assert.equal(sanitizeUserId('10001'), '10001')
  assert.equal(sanitizeUserId('user.name'), 'user.name')
})

test('SEC-14: resolveUserDir / isUserPath block ../ empNo', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'uds-ws-'))
  try {
    const root = resolveWorkspaceRoot(dir)
    assert.equal(resolveUserDir(root, '../escape'), null)
    assert.equal(resolveUserDir(root, '10001')?.endsWith('10001') || resolveUserDir(root, '10001')?.includes('10001'), true)

    const store = new UserWorkspaceStore({})
    assert.equal(store.isUserPath('../escape', join(root, 'x'), root), false)
    assert.equal(store.isUserPath('10001', join(root, '10001', 'a'), root), true)
    // Outside user dir
    assert.equal(store.isUserPath('10001', join(root, '10002'), root), false)
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('SEC-26: setRole cannot assign fallback_admin', async () => {
  const store = new RolesStore({})
  store._roles.set('admin1', ROLES.ADMIN)
  await assert.rejects(
    () => store.setRole('u1', ROLES.FALLBACK_ADMIN, ROLES.ADMIN),
    (err) => err.code === 'invalid_role_params',
  )
  await store.setRole('u1', ROLES.USER, ROLES.ADMIN)
  assert.equal(store.getRole('u1'), ROLES.USER)
})

test('SEC-10: live rolesStore demotion removes view-all', () => {
  const store = new RolesStore()
  store._roles.set('boss', ROLES.SUPER_ADMIN)
  const ownersMap = new Map([['s-peer', 'u2']])
  const access = createSessionAccess({
    sessionAcl: { getOwner: (id) => ownersMap.get(String(id)) || null },
    userWorkspaces: { get: () => null, isUserPath: () => false },
    getWorkspaceRoot: () => '/ws',
    getWorkspaceRegistry: () => ({ list: () => [] }),
    rolesStore: store,
  })
  const identity = {
    empNo: 'boss',
    role: 'super_admin',
    permissions: computePermissions('super_admin', { viewAllSessions: true }),
  }
  assert.equal(access.canAccessSession('s-peer', identity), true)
  // Demote in store; frozen identity.permissions still look admin — live check wins.
  store._roles.set('boss', ROLES.USER)
  assert.equal(access.canSeeAll(identity), false)
  assert.equal(access.canAccessSession('s-peer', identity), false)
})
