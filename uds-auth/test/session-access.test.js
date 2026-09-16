import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { createSessionAccess } from '../lib/dsh-acl.js'
import { computePermissions, RolesStore, ROLES } from '../lib/roles.js'

function makeAccess(owners = {}) {
  const ownersMap = new Map(Object.entries(owners))
  const userPaths = new Map([
    ['u1', { path: '/ws/u1', workspaceId: 'ws-u1' }],
    ['u2', { path: '/ws/u2', workspaceId: 'ws-u2' }],
  ])
  return createSessionAccess({
    sessionAcl: {
      getOwner(id) {
        return ownersMap.get(String(id)) || null
      },
    },
    userWorkspaces: {
      get(empNo) {
        return userPaths.get(String(empNo)) || null
      },
      isUserPath(empNo, candidate, root) {
        const row = userPaths.get(String(empNo))
        if (!row?.path || !candidate) return false
        const base = String(row.path).replace(/\\/g, '/').replace(/\/+$/, '')
        const path = String(candidate).replace(/\\/g, '/')
        return path === base || path.startsWith(base + '/')
      },
    },
    getWorkspaceRoot: () => '/ws',
    getWorkspaceRegistry: () => ({
      list: () => ([
        { id: 'ws-u1', path: '/ws/u1', sessionIds: ['s-in-u1'] },
        { id: 'ws-u2', path: '/ws/u2', sessionIds: ['s-in-u2'] },
        { id: 'ws-shared', path: '/ws/shared', sessionIds: ['s-shared'] },
      ]),
    }),
  })
}

describe('createSessionAccess', () => {
  it('super/fallback see all by default via rolesStore prefs (default on)', () => {
    const store = new RolesStore()
    store._roles.set('boss', ROLES.SUPER_ADMIN)
    const { canAccessSession, canSeeAll } = createSessionAccess({
      sessionAcl: { getOwner: () => 'u2' },
      userWorkspaces: { get: () => null, isUserPath: () => false },
      getWorkspaceRoot: () => '/ws',
      getWorkspaceRegistry: () => ({ list: () => [] }),
      rolesStore: store,
    })
    const superAdmin = { empNo: 'boss', role: 'super_admin', permissions: computePermissions('super_admin') }
    const fallback = { empNo: 'administrator', role: 'fallback_admin', permissions: computePermissions('fallback_admin') }
    assert.equal(canSeeAll(superAdmin), true)
    assert.equal(canSeeAll(fallback), true)
    assert.equal(canAccessSession('s-other', superAdmin), true)

    store.setViewAllSessions('boss', false)
    assert.equal(canSeeAll(superAdmin), false)
    assert.equal(canAccessSession('s-other', superAdmin), false)
  })

  it('admin-class sees all by default; user only owned or own-workspace sessions', () => {
    const { canAccessSession, canSeeAll } = makeAccess({
      's-owned': 'u1',
      's-peer': 'u2',
    })
    const admin = {
      empNo: 'u1',
      role: 'admin',
      permissions: computePermissions('admin', { viewAllSessions: true }),
    }
    const user = {
      empNo: 'u1',
      role: 'user',
      permissions: computePermissions('user'),
    }
    assert.equal(canSeeAll(admin), true)
    assert.equal(canSeeAll(user), false)
    assert.equal(admin.permissions.canToggleViewAllSessions, true)
    assert.equal(user.permissions.canToggleViewAllSessions, false)

    assert.equal(canAccessSession('s-owned', admin), true)
    assert.equal(canAccessSession('s-peer', admin), true)
    assert.equal(canAccessSession('s-in-u1', user), true)
    assert.equal(canAccessSession('s-cwd', user, { cwd: '/ws/u1/project' }), true)

    assert.equal(canAccessSession('s-in-u2', user), false)
    assert.equal(canAccessSession('s-shared', user), false)
    assert.equal(canAccessSession('s-cwd-peer', user, { cwd: '/ws/u2/x' }), false)
  })

  it('admin can turn off view-all via preference (same as super_admin)', () => {
    const store = new RolesStore()
    store._roles.set('op', ROLES.ADMIN)
    store.setViewAllSessions('op', false)
    const ownersMap = new Map([['s-peer', 'u2']])
    const access = createSessionAccess({
      sessionAcl: { getOwner: (id) => ownersMap.get(String(id)) || null },
      userWorkspaces: { get: () => null, isUserPath: () => false },
      getWorkspaceRoot: () => '/ws',
      getWorkspaceRegistry: () => ({ list: () => [] }),
      rolesStore: store,
    })
    const admin = {
      empNo: 'op',
      role: 'admin',
      permissions: computePermissions('admin', { viewAllSessions: true }),
    }
    assert.equal(access.canSeeAll(admin), false)
    assert.equal(access.canAccessSession('s-peer', admin), false)
    assert.equal(store.resolvePermissions('op').canToggleViewAllSessions, true)
  })

  it('missing owner does not deny when cwd is under user path', () => {
    const { canAccessSession } = makeAccess({})
    const user = { empNo: 'u1', role: 'user', permissions: computePermissions('user') }
    assert.equal(canAccessSession('legacy', user, { cwd: '/ws/u1' }), true)
    assert.equal(canAccessSession('legacy-other', user, { cwd: '/ws/u2' }), false)
  })

  it('admin can see unowned channel/system sessions outside user-workspaces', () => {
    const store = new RolesStore()
    store._roles.set('u1', ROLES.ADMIN)
    store.setViewAllSessions('u1', false)
    const accessOff = createSessionAccess({
      sessionAcl: { getOwner: () => null },
      userWorkspaces: {
        get: () => null,
        isUserPath: () => false,
      },
      getWorkspaceRoot: () => '/ws',
      getWorkspaceRegistry: () => ({ list: () => [] }),
      rolesStore: store,
    })
    const admin = {
      empNo: 'u1',
      role: 'admin',
      permissions: computePermissions('admin', { viewAllSessions: false }),
    }
    const user = {
      empNo: 'u1',
      role: 'user',
      permissions: computePermissions('user'),
    }
    assert.equal(accessOff.canAccessSession('ch-1', admin, { cwd: '/bots/whatsapp' }), true)
    assert.equal(accessOff.canAccessSession('ch-1', user, { cwd: '/bots/whatsapp' }), false)
    assert.equal(accessOff.canAccessSession('s-peer', admin, { cwd: '/ws/u2/x' }), false)

    const ownersMap = new Map([['ch-owned', 'u2']])
    const accessOwned = createSessionAccess({
      sessionAcl: { getOwner: (id) => ownersMap.get(String(id)) || null },
      userWorkspaces: { get: () => null, isUserPath: () => false },
      getWorkspaceRoot: () => '/ws',
      getWorkspaceRegistry: () => ({ list: () => [] }),
      rolesStore: store,
    })
    assert.equal(accessOwned.canAccessSession('ch-owned', admin, { cwd: '/bots/wa' }), false)

    assert.equal(accessOff.isVisibleWorkspace(admin, { id: 'bot-ws', path: '/bots/whatsapp' }), true)
    assert.equal(accessOff.isVisibleWorkspace(user, { id: 'bot-ws', path: '/bots/whatsapp' }), false)
  })

  it('live rolesStore prefs override stale identity.permissions', () => {
    const store = new RolesStore()
    store._roles.set('boss', ROLES.SUPER_ADMIN)
    store.setViewAllSessions('boss', false)
    const ownersMap = new Map([['s-peer', 'u2']])
    const access = createSessionAccess({
      sessionAcl: { getOwner: (id) => ownersMap.get(String(id)) || null },
      userWorkspaces: {
        get: () => null,
        isUserPath: () => false,
      },
      getWorkspaceRoot: () => '/ws',
      getWorkspaceRegistry: () => ({ list: () => [] }),
      rolesStore: store,
    })
    const stale = {
      empNo: 'boss',
      role: 'super_admin',
      permissions: computePermissions('super_admin', { viewAllSessions: true }),
    }
    assert.equal(access.canSeeAll(stale), false)
    assert.equal(access.canAccessSession('s-peer', stale), false)

    store.setViewAllSessions('boss', true)
    assert.equal(access.canSeeAll(stale), true)
    assert.equal(access.canAccessSession('s-peer', stale), true)
  })
})

describe('RolesStore view-all prefs', () => {
  it('defaults on for admin-class and can be turned off', () => {
    const store = new RolesStore()
    store._roles.set('boss', ROLES.SUPER_ADMIN)
    store._roles.set('op', ROLES.ADMIN)

    assert.equal(store.isViewAllSessionsEnabled('boss'), true)
    assert.equal(store.resolvePermissions('boss').canViewAllSessions, true)
    assert.equal(store.resolvePermissions('boss').canToggleViewAllSessions, true)

    store.setViewAllSessions('boss', false)
    assert.equal(store.isViewAllSessionsEnabled('boss'), false)
    assert.equal(store.resolvePermissions('boss').canViewAllSessions, false)

    store.setViewAllSessions('boss', true)
    assert.equal(store.resolvePermissions('boss').canViewAllSessions, true)

    assert.equal(store.resolvePermissions('op').canToggleViewAllSessions, true)
    assert.equal(store.resolvePermissions('op').canViewAllSessions, true)
    store.setViewAllSessions('op', false)
    assert.equal(store.resolvePermissions('op').canViewAllSessions, false)
  })

  it('rejects view-all toggle for ordinary users', () => {
    const store = new RolesStore()
    store._roles.set('u1', ROLES.USER)
    assert.throws(() => store.setViewAllSessions('u1', true), (err) => err.code === 'forbidden_view_all_sessions')
  })

  it('admin-class roles share create-workspace and manage-users permissions', () => {
    for (const role of [ROLES.SUPER_ADMIN, ROLES.FALLBACK_ADMIN, ROLES.ADMIN]) {
      const p = computePermissions(role, { viewAllSessions: true })
      assert.equal(p.canCreateWorkspace, true)
      assert.equal(p.canManageUsers, true)
      assert.equal(p.canAccessSettings, true)
      assert.equal(p.canToggleViewAllSessions, true)
      assert.equal(p.canViewAllSessions, true)
    }
    assert.equal(computePermissions(ROLES.USER).canCreateWorkspace, false)
    assert.equal(computePermissions(ROLES.USER).canManageUsers, false)
  })
})
