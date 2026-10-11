import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { RolesStore, ROLES } from '../lib/roles.js'
import {
  classifyAuthKind,
  identityFromSessionRecord,
  createSessionAccess,
} from '../lib/dsh-acl.js'
import {
  buildLocalAdminUserContext,
  sealLocalAdminBox,
  isLocalAdminBoxConfigured,
} from '../lib/local-admin.js'
import { MemoryStore } from '../lib/session/memory-store.js'
import { UserWorkspaceStore } from '../lib/workspace-provision.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')

test('A08: sealed_box identity survives when emergency password is disabled', async () => {
  process.env.UDS_AUTH_LOCAL_ADMIN_BOX = sealLocalAdminBox('test-passphrase-ok')
  assert.equal(isLocalAdminBoxConfigured(), true)

  const roles = new RolesStore({})
  roles._fallbackPasswordHash = null
  roles._prefs.set('administrator', { viewAllSessions: true })
  assert.equal(roles.isFallbackEnabled(), false)

  const store = new MemoryStore()
  const { bearer } = await store.create(buildLocalAdminUserContext(), 600)
  const session = store.getByBearerSync(bearer)
  assert.equal(session.kind, 'sealed_box')

  const id = identityFromSessionRecord(session, roles)
  assert.ok(id)
  assert.equal(id.kind, 'sealed_box')
  assert.equal(id.permissions.canCreateWorkspace, true)
  assert.equal(id.permissions.canViewAllSessions, true)

  // Incomplete ALS identity must still classify via live session row fields.
  assert.equal(classifyAuthKind(session, 'administrator'), 'sealed_box')
  assert.equal(
    classifyAuthKind({ empNo: 'administrator' }, 'administrator'),
    'fallback',
  )
})

test('sealed_box admin still sees shared workspaces when view-all is on', async () => {
  process.env.UDS_AUTH_LOCAL_ADMIN_BOX = sealLocalAdminBox('test-passphrase-ok')
  const roles = new RolesStore({})
  roles._fallbackPasswordHash = null
  roles._prefs.set('administrator', { viewAllSessions: true })

  const store = new MemoryStore()
  const { bearer } = await store.create(buildLocalAdminUserContext(), 600)
  const identity = identityFromSessionRecord(store.getByBearerSync(bearer), roles)

  const uw = new UserWorkspaceStore({})
  uw.set('administrator', {
    path: 'C:\\Users\\zhout\\.dsh\\user-workspaces\\administrator',
    workspaceId: 'ws-admin',
  })
  const access = createSessionAccess({
    sessionAcl: { getOwner: () => null },
    userWorkspaces: uw,
    getWorkspaceRoot: () => 'C:\\Users\\zhout\\.dsh\\user-workspaces',
    rolesStore: roles,
    getWorkspaceRegistry: () => ({ list: () => [] }),
  })
  assert.equal(access.canSeeAll(identity), true)
  assert.equal(
    access.isVisibleWorkspace(identity, { id: 'ws-harness', path: 'D:\\project\\harness' }),
    true,
  )
})

test('assertPrincipalLive prefers session.kind sealed_box over bare administrator identity', () => {
  const src = readFileSync(join(root, 'lib/dsh-acl.js'), 'utf8')
  assert.match(src, /classifyAuthKind\(sessionRow \|\| identity/)
  assert.match(src, /incomplete ALS identities/)
  assert.doesNotMatch(
    src,
    /emp === 'administrator' && kind !== 'uds'/,
  )
})

test('Desktop WS ticket mint prefetches via fetch then sync cache', () => {
  const src = readFileSync(join(root, 'lib/client.js'), 'utf8')
  assert.match(src, /prefetchWsTickets/)
  assert.match(src, /reconnectWithWsTicket/)
  assert.match(src, /_wsTicketCache/)
  assert.match(src, /udsBridgeToken/)
  assert.match(src, /data-uds-session-only/)
  assert.match(src, /getDesktopTransportBase\(\)/)
  assert.match(src, /new URL\('\/uds-auth\/api\/ws-ticket', transport\)/)
  assert.match(src, /WS ticket mint failed/)
  assert.match(src, /__udsAuthWsAuthedOnce/)
  // Reconnect storm must be coalesced — second ticketed reconnect kills the stream.
  assert.match(src, /_softReconnectQuietUntil/)
  assert.match(src, /WorkspaceStateStream/)
  assert.match(src, /!window\.__udsAuthWsAuthedOnce/)
})

test('workspace follow yields empty baseline for anonymous (Desktop must not die)', () => {
  const src = readFileSync(join(root, 'lib/dsh-acl.js'), 'utf8')
  assert.match(src, /emptyWorkspaceBaseline/)
  assert.match(src, /holdUntilAbort/)
  assert.match(src, /ended before its opening snapshot/)
  assert.match(src, /未分组/)
  // Must not early-return with zero frames for anonymous browsers.
  assert.doesNotMatch(src, /if \(!empOf\(identity\)\) return\n\s*\/\/ R04/)
})

test('classifyAuthKind keeps local-admin-unlock as sealed_box', () => {
  assert.equal(
    classifyAuthKind({ authMode: 'local-admin-unlock', empNo: 'administrator' }),
    'sealed_box',
  )
  assert.equal(
    classifyAuthKind({ kind: 'sealed_box', empNo: 'administrator' }),
    'sealed_box',
  )
  assert.equal(
    classifyAuthKind({ kind: 'fallback', empNo: 'administrator' }),
    'fallback',
  )
  assert.equal(ROLES.FALLBACK_ADMIN, 'fallback_admin')
})
