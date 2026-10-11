/**
 * Per-user workspace provisioning under workspaceRoot/<empNo>.
 */
import { mkdir } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { homedir } from 'node:os'
import { readFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { withUserContext, getUserContext } from './context.js'
import { sanitizeUserId, resolveUserDir, isPathInside } from './utils/safe-userid.js'
import { atomicWriteJson } from './utils/atomic-write.js'

function defaultWorkspaceRoot() {
  const home = process.env.DSH_HOME || process.env.DSH_PROFILE_DIR || join(homedir(), '.dsh')
  return join(home, 'user-workspaces')
}

/**
 * @param {string|undefined} configured
 */
export function resolveWorkspaceRoot(configured) {
  const raw = (configured && String(configured).trim()) || defaultWorkspaceRoot()
  return resolve(raw)
}

export class UserWorkspaceStore {
  /**
   * @param {{ mapFile?: string }} options
   */
  constructor(options = {}) {
    this._map = new Map() // empNo → { path, workspaceId }
    this._mapFile = options.mapFile ? resolve(options.mapFile) : null
    this._dirty = false
    this._saveTimer = null
  }

  async init() {
    if (!this._mapFile) return
    try {
      const raw = await readFile(this._mapFile, 'utf-8')
      const data = JSON.parse(raw)
      for (const [empNo, row] of Object.entries(data.users || {})) {
        if (row?.path) this._map.set(String(empNo), { path: String(row.path), workspaceId: row.workspaceId || null })
      }
    } catch (err) {
      if (err.code !== 'ENOENT') console.warn('[uds-auth:UserWorkspace] load failed:', err.message)
    }
  }

  _markDirty() {
    this._dirty = true
    if (this._saveTimer) return
    this._saveTimer = setTimeout(() => { void this._save() }, 1500)
  }

  async _save() {
    this._saveTimer = null
    if (!this._dirty || !this._mapFile) return
    this._dirty = false
    try {
      await atomicWriteJson(this._mapFile, {
        users: Object.fromEntries(this._map),
        savedAt: new Date().toISOString(),
      }, { mode: 0o600 })
    } catch (err) {
      this._dirty = true
      console.warn('[uds-auth:UserWorkspace] save failed:', err.message)
    }
  }

  get(empNo) {
    return this._map.get(String(empNo)) || null
  }

  set(empNo, row) {
    this._map.set(String(empNo), row)
    this._markDirty()
  }

  /**
   * Ensure directory + registry entry for empNo.
   * @param {object} ctx - cordis context with workspaceRegistry
   * @param {string} workspaceRoot
   * @param {string} empNo
   */
  async ensureUserWorkspace(ctx, workspaceRoot, empNo) {
    if (!empNo || empNo === 'administrator') {
      // Fallback admin: still get a dedicated folder
      empNo = empNo || 'administrator'
    }
    const safeId = sanitizeUserId(empNo)
    if (!safeId) {
      console.warn('[uds-auth] reject unsafe empNo for workspace:', String(empNo).slice(0, 32))
      return null
    }
    empNo = safeId
    const root = resolveWorkspaceRoot(workspaceRoot)
    const userPath = resolveUserDir(root, empNo)
    if (!userPath) return null
    await mkdir(userPath, { recursive: true })

    // Cordis throws on ctx.workspaceRegistry without inject.
    // apply() passes { workspaceRegistryHandle } from an injected fiber.
    let registry = ctx && ctx.workspaceRegistryHandle
    if (!registry && ctx && typeof ctx.get === 'function') {
      try { registry = ctx.get('workspaceRegistry') } catch { registry = undefined }
    }

    const cached = this.get(empNo)
    if (registry && cached?.workspaceId && typeof registry.get === 'function') {
      try {
        const existing = registry.get(cached.workspaceId)
        if (existing) {
          return { path: cached.path || userPath, workspaceId: String(cached.workspaceId), workspace: existing }
        }
      } catch { /* fall through and recreate */ }
    }

    if (!registry || typeof registry.create !== 'function') {
      console.warn('[uds-auth] workspaceRegistry unavailable; mkdir only:', userPath)
      this.set(empNo, { path: userPath, workspaceId: cached?.workspaceId || null })
      return { path: userPath, workspaceId: cached?.workspaceId || null, workspace: null }
    }

    const prev = getUserContext()
    const workspace = await withUserContext(
      { ...(prev || {}), empNo, _internalProvision: true },
      () => registry.create(userPath, String(empNo)),
    )
    const workspaceId = workspace?.id != null ? String(workspace.id) : null
    this.set(empNo, { path: userPath, workspaceId })
    return { path: userPath, workspaceId, workspace }
  }

  /** Path prefix check: is this path under the user's provisioned dir? */
  isUserPath(empNo, candidatePath, workspaceRoot) {
    if (!empNo || !candidatePath) return false
    const root = resolveWorkspaceRoot(workspaceRoot)
    const userPath = resolveUserDir(root, empNo)
    if (!userPath) return false
    // Candidate must stay under user dir; user dir must stay under workspace root.
    if (!isPathInside(root, userPath)) return false
    return isPathInside(userPath, candidatePath)
  }
}

export { sanitizeUserId, resolveUserDir }
