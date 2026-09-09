import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { createSessionAccess } from '../lib/dsh-acl.js'

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
  it('super_admin and administrator see all sessions', () => {
    const { canAccessSession, canSeeAll } = makeAccess({ 's-other': 'u2' })
    const superAdmin = {
      empNo: 'boss',
      role: 'super_admin',
      permissions: { canViewAllSessions: true },
    }
    const fallback = {
      empNo: 'administrator',
      role: 'fallback_admin',
      permissions: { canViewAllSessions: true },
    }
    assert.equal(canSeeAll(superAdmin), true)
    assert.equal(canSeeAll(fallback), true)
    assert.equal(canAccessSession('s-other', superAdmin), true)
    assert.equal(canAccessSession('s-other', fallback), true)
  })

  it('admin and user only see owned or own-workspace sessions', () => {
    const { canAccessSession, canSeeAll } = makeAccess({
      's-owned': 'u1',
      's-peer': 'u2',
    })
    const admin = {
      empNo: 'u1',
      role: 'admin',
      permissions: { canViewAllSessions: false, canAccessSettings: true },
    }
    const user = {
      empNo: 'u1',
      role: 'user',
      permissions: { canViewAllSessions: false },
    }
    assert.equal(canSeeAll(admin), false)
    assert.equal(canSeeAll(user), false)

    assert.equal(canAccessSession('s-owned', admin), true)
    assert.equal(canAccessSession('s-in-u1', user), true)
    assert.equal(canAccessSession('s-cwd', user, { cwd: '/ws/u1/project' }), true)

    assert.equal(canAccessSession('s-peer', admin), false)
    assert.equal(canAccessSession('s-in-u2', user), false)
    assert.equal(canAccessSession('s-shared', user), false)
    assert.equal(canAccessSession('s-cwd-peer', user, { cwd: '/ws/u2/x' }), false)
  })

  it('missing owner does not deny when cwd is under user path', () => {
    const { canAccessSession } = makeAccess({})
    const user = { empNo: 'u1', role: 'user', permissions: { canViewAllSessions: false } }
    assert.equal(canAccessSession('legacy', user, { cwd: '/ws/u1' }), true)
    assert.equal(canAccessSession('legacy-other', user, { cwd: '/ws/u2' }), false)
  })
})
