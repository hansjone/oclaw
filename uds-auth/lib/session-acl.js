/**
 * Session ownership store — sessionId → empNo.
 *
 * Used with workspace/cwd checks in dsh-acl.js (owner OR own workspace).
 * Missing owner must NOT deny access by itself (legacy sessions).
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { getUserContext } from './context.js'
import { ROLES, computePermissions } from './roles.js'

export class SessionAclStore {
  /**
   * @param {{ ownersFile?: string }} options
   */
  constructor(options = {}) {
    this._owners = new Map()
    this._ownersFile = options.ownersFile ? resolve(options.ownersFile) : null
    this._dirty = false
    this._saveTimer = null
  }

  async init() {
    if (!this._ownersFile) return
    try {
      const raw = await readFile(this._ownersFile, 'utf-8')
      const data = JSON.parse(raw)
      for (const [sessionId, empNo] of Object.entries(data.owners || {})) {
        this._owners.set(String(sessionId), String(empNo))
      }
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn('[uds-auth:SessionAcl] load failed:', err.message)
      }
    }
  }

  _markDirty() {
    this._dirty = true
    if (this._saveTimer) return
    this._saveTimer = setTimeout(() => { void this._save() }, 1500)
  }

  async _save() {
    this._saveTimer = null
    if (!this._dirty || !this._ownersFile) return
    this._dirty = false
    try {
      await mkdir(dirname(this._ownersFile), { recursive: true })
      await writeFile(
        this._ownersFile,
        JSON.stringify({
          owners: Object.fromEntries(this._owners),
          savedAt: new Date().toISOString(),
        }, null, 2),
        'utf-8',
      )
    } catch (err) {
      console.warn('[uds-auth:SessionAcl] save failed:', err.message)
    }
  }

  getOwner(sessionId) {
    return this._owners.get(String(sessionId)) || null
  }

  setOwner(sessionId, empNo) {
    if (!sessionId || !empNo) return
    this._owners.set(String(sessionId), String(empNo))
    this._markDirty()
  }

  /** All stamped owners for export / analytics. */
  listOwners() {
    return Array.from(this._owners.entries()).map(([sessionId, empNo]) => ({ sessionId, empNo }))
  }

  /**
   * Filter list/search payloads with an external access predicate.
   * @param {{ items?: Array<{ sessionId?: string, id?: string }> }} value
   * @param {(sessionId: string, row: object) => boolean} canAccess
   */
  filterListValue(value, canAccess) {
    if (!value || !Array.isArray(value.items)) return value
    const pred = typeof canAccess === 'function' ? canAccess : () => false
    return {
      ...value,
      items: value.items.filter((row) => {
        const id = row?.sessionId ?? row?.id
        return id != null && pred(String(id), row)
      }),
    }
  }
}

/**
 * Resolve identity for ACL checks (null = anonymous).
 * @param {import('./roles.js').RolesStore} rolesStore
 */
export function identityFromAls(rolesStore) {
  const ctx = getUserContext()
  if (!ctx?.empNo) return null
  const role = ctx.role || rolesStore.getRole(ctx.empNo)
  return {
    empNo: ctx.empNo,
    role,
    permissions: ctx.permissions || computePermissions(role),
  }
}

export function isSuperLike(role) {
  return role === ROLES.SUPER_ADMIN || role === ROLES.FALLBACK_ADMIN
}
