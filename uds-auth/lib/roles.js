/**
 * uds-auth 角色存储 + 权限管理
 *
 * 角色（身份标签；admin 级权限相同 — SEC-26 产品决策：当前同权）:
 *   super_admin     身份：显式初始管理员 / 管理 API 提权；权限 = admin 级
 *   fallback_admin  身份：仅应急账号 administrator（不可经管理 API 分配）；权限 = admin 级
 *   admin           身份：用户管理中提权；权限 = admin 级
 *   user            仅看自己会话，无设置 / 不可建工作区
 *
 * admin 级（isAdminClass）权限相同：用户管理、设置、建工作区、默认可看全部会话。
 * 「超管」是身份标签，不是更强权限隔离；viewAllSessions 是显示偏好，非安全边界。
 * 持久化: roles.json (roles + prefs + fallbackPasswordHash)
 */
import { createHash, randomBytes, scryptSync, timingSafeEqual } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { ROLE_LABELS_ZH } from './i18n.js'
import { atomicWriteJson } from './utils/atomic-write.js'
import { hashPasswordAsync, verifyScryptAsync } from './utils/password-kdf.js'

function codedError(code) {
  const err = new Error(code)
  err.code = code
  return err
}

const ACCOUNT_STATUS = {
  ACTIVE: 'active',
  DISABLED: 'disabled',
}

/** Known shared default from pre-0.3 installs — must never remain usable (R10). */
const LEGACY_DEFAULT_SHA256 = createHash('sha256').update('Admin@123').digest('hex')

/**
 * R10: versioned scrypt password hash.
 * Format: scrypt$N$r$p$saltB64$urlHashB64
 * Legacy bare SHA-256 hex still verifies once, then must be rotated (except known default).
 */
function hashPasswordScrypt(password, saltBuf = randomBytes(16)) {
  const N = 16384
  const r = 8
  const p = 1
  const derived = scryptSync(String(password), saltBuf, 32, { N, r, p })
  return [
    'scrypt',
    String(N),
    String(r),
    String(p),
    saltBuf.toString('base64url'),
    derived.toString('base64url'),
  ].join('$')
}

function verifyPasswordHash(password, stored) {
  const s = String(stored || '')
  if (!s) return false
  if (s.startsWith('scrypt$')) {
    const parts = s.split('$')
    if (parts.length !== 6) return false
    const N = Number(parts[1])
    const r = Number(parts[2])
    const p = Number(parts[3])
    const salt = Buffer.from(parts[4], 'base64url')
    const expect = Buffer.from(parts[5], 'base64url')
    if (N !== 16384 || r !== 8 || p !== 1 || salt.length !== 16 || expect.length !== 32) return false
    let derived
    try {
      derived = scryptSync(String(password), salt, expect.length, { N, r, p })
    } catch {
      return false
    }
    if (derived.length !== expect.length) return false
    return timingSafeEqual(derived, expect)
  }
  // Legacy unsalted SHA-256 — reject known shared default outright.
  if (/^[0-9a-f]{64}$/i.test(s)) {
    if (s.toLowerCase() === LEGACY_DEFAULT_SHA256) return false
    const got = createHash('sha256').update(String(password)).digest('hex')
    try {
      return timingSafeEqual(Buffer.from(got, 'hex'), Buffer.from(s, 'hex'))
    } catch {
      return false
    }
  }
  return false
}

/** @deprecated keep name for call sites that still import hashPassword */
function hashPassword(password) {
  return hashPasswordScrypt(password)
}

export const ROLES = {
  SUPER_ADMIN: 'super_admin',
  ADMIN: 'admin',
  USER: 'user',
  FALLBACK_ADMIN: 'fallback_admin', // 特殊，UAC 挂了时用，等同 super_admin 权限
}

/** zh labels for list/search; UI should translate via i18n role.* keys. */
export const ROLE_LABELS = ROLE_LABELS_ZH

/** admin 级身份：超管 / 应急 / 管理员（权限相同，仅身份标签不同） */
export function isAdminClass(role) {
  return role === ROLES.SUPER_ADMIN
    || role === ROLES.FALLBACK_ADMIN
    || role === ROLES.ADMIN
}

/**
 * 计算角色权限 (纯函数)
 * @param {string} role
 * @param {{ viewAllSessions?: boolean }} [opts] 个人偏好；admin 级默认可见全部
 */
export function computePermissions(role, opts = {}) {
  const viewAll = !!opts.viewAllSessions
  if (isAdminClass(role)) {
    return {
      canManageUsers: true,
      canAccessSettings: true,
      canToggleViewAllSessions: true,
      canViewAllSessions: viewAll,
      canViewSystemSessions: true,
      canCreateWorkspace: true,
    }
  }
  // user / undefined
  return {
    canManageUsers: false,
    canAccessSettings: false,
    canToggleViewAllSessions: false,
    canViewAllSessions: false,
    canViewSystemSessions: false,
    canCreateWorkspace: false,
  }
}

/** 角色是否允许开启「查看全部会话」（admin 级） */
export function canToggleViewAllSessions(role) {
  return isAdminClass(role)
}

/** Historical default — never enable automatically (R10). */
export const DEFAULT_FALLBACK_PASSWORD = 'Admin@123'
export const DEFAULT_FALLBACK_USERNAME = 'administrator'

/**
 * RolesStore — 角色存储
 * 内存 Map + 可选 JSON 文件持久化
 *
 * fallback admin: 默认关闭；须在设置中显式设置 scrypt 口令（≥10，禁 Admin@123）。
 *   登录路径: POST /uds-auth/api/fallback/login { username, password }
 */
export class RolesStore {
  constructor(options = {}) {
    this._roles = new Map()              // empNo → role
    this._prefs = new Map()              // empNo → { viewAllSessions?: boolean }
    this._status = new Map()             // empNo → active|disabled (R12)
    this._firstBootLock = Promise.resolve()
    this._mutateChain = Promise.resolve() // R09: serialize role mutations
    this._saveChain = Promise.resolve()
    this._rolesFile = options.rolesFile ? resolve(options.rolesFile) : null
    this._fallbackPasswordHash = null     // scrypt$… or legacy hex；null = 未启用
    this._fallbackNeedsRehash = false
    this._fallbackCredVersion = 0         // F02: bumps on set/clear password
    this._committedFallback = { hash: null, needs: false, ver: 0 }
    this._fallbackRateLimit = new Map()   // ip → { count, resetAt }
    this._dirty = false
    this._saveTimer = null
  }

  /**
   * New installs do NOT enable a shared default password (SEC-08).
   * Admins must set a password explicitly via settings / setFallbackPassword.
   */
  _ensureDefaultFallback() {
    // no-op — kept for call-site compatibility
  }

  // === 持久化 ===

  async init() {
    let loadedOk = false
    if (this._rolesFile) {
      try {
        const raw = await readFile(this._rolesFile, 'utf-8')
        const data = JSON.parse(raw)
        for (const [empNo, role] of Object.entries(data.roles || {})) {
          this._roles.set(empNo, role)
        }
        for (const [empNo, prefs] of Object.entries(data.prefs || {})) {
          if (prefs && typeof prefs === 'object') {
            this._prefs.set(String(empNo), { ...prefs })
          }
        }
        if (Object.prototype.hasOwnProperty.call(data, 'fallbackPasswordHash')) {
          this._fallbackPasswordHash = data.fallbackPasswordHash || null
        }
        this._fallbackCredVersion = Number.isSafeInteger(data.fallbackCredVersion)
          && data.fallbackCredVersion >= 0 ? data.fallbackCredVersion : 0
        for (const [empNo, st] of Object.entries(data.status || {})) {
          if (st === ACCOUNT_STATUS.DISABLED || st === ACCOUNT_STATUS.ACTIVE) {
            this._status.set(String(empNo), st)
          }
        }
        loadedOk = true
      } catch (err) {
        if (err.code === 'ENOENT') {
          // First boot — empty roles, fallback disabled until explicitly configured.
          console.info(
            '[uds-auth] roles file missing; fallback password disabled until configured'
            + ` (set initialAdmin via UDS_AUTH_INITIAL_ADMIN)`,
          )
        } else {
          // Corrupt roles must NOT restore a default password (SEC-08/21).
          console.error('[uds-auth:RolesStore] Failed to load roles file — refusing default password:', err.message)
          this._loadFailed = true
        }
      }
    }
    // R10: known shared default hash cannot remain enabled after upgrade.
    if (loadedOk && this._fallbackPasswordHash
      && String(this._fallbackPasswordHash).toLowerCase() === LEGACY_DEFAULT_SHA256) {
      console.warn('[uds-auth] refusing legacy shared default fallback password — disabled until reset')
      this._fallbackPasswordHash = null
      this._dirty = true
      await this._save()
    } else if (loadedOk && this._fallbackPasswordHash
      && /^[0-9a-f]{64}$/i.test(String(this._fallbackPasswordHash))) {
      this._fallbackNeedsRehash = true
      console.warn('[uds-auth] legacy SHA-256 fallback hash loaded — will upgrade on next successful login')
    }
    if (loadedOk && this._fallbackPasswordHash) {
      console.info('[uds-auth] fallback_admin password loaded from roles file')
    }
    this._captureCommittedFallback()
  }

  get loadFailed() {
    return !!this._loadFailed
  }

  _markDirty() {
    this._dirty = true
    if (this._saveTimer) return
    this._saveTimer = setTimeout(() => {
      this._saveTimer = null
      void this._withMutationLock(() => this.flush()).catch(() => {})
    }, 2000)
    this._saveTimer.unref?.()
  }

  /** Flush pending roles/prefs to disk immediately (e.g. view-all toggle). */
  async flush() {
    if (this._saveTimer) {
      clearTimeout(this._saveTimer)
      this._saveTimer = null
    }
    await this._save()
  }

  async _save() {
    const run = this._saveChain.then(() => this._saveNow())
    this._saveChain = run.catch(() => {})
    return run
  }

  async _saveNow() {
    this._saveTimer = null
    if (!this._dirty || !this._rolesFile) return
    const snapshot = {
      roles: Object.fromEntries(this._roles),
      prefs: Object.fromEntries(this._prefs),
      status: Object.fromEntries(this._status),
      fallbackPasswordHash: this._fallbackPasswordHash,
      fallbackCredVersion: this._fallbackCredVersion,
      savedAt: new Date().toISOString(),
    }
    this._dirty = false
    try {
      await atomicWriteJson(this._rolesFile, snapshot, { mode: 0o600 })
    } catch (err) {
      this._dirty = true
      console.error('[uds-auth:RolesStore] Failed to save roles file:', err.message)
      const e = new Error('roles_persist_failed')
      e.code = 'roles_persist_failed'
      e.cause = err
      throw e
    }
    // Changes during await writeFile — schedule another save.
    if (this._dirty) this._markDirty()
  }

  /** R09: serialize mutations that check last-admin invariants. */
  _withMutationLock(fn) {
    const transaction = async () => {
      const previous = {
        roles: new Map(this._roles), prefs: new Map(this._prefs), status: new Map(this._status),
        hash: this._fallbackPasswordHash, needs: this._fallbackNeedsRehash,
        ver: this._fallbackCredVersion,
      }
      this._transactionSnapshot = previous
      try {
        return await fn()
      } catch (err) {
        this._roles = previous.roles
        this._prefs = previous.prefs
        this._status = previous.status
        this._fallbackPasswordHash = previous.hash
        this._fallbackNeedsRehash = previous.needs
        this._fallbackCredVersion = previous.ver
        this._dirty = false
        if (this._saveTimer) clearTimeout(this._saveTimer)
        this._saveTimer = null
        throw err
      } finally {
        this._transactionSnapshot = null
      }
    }
    const run = this._mutateChain.then(transaction, transaction)
    this._mutateChain = run.then(() => {}, () => {})
    return run
  }

  getAccountStatus(empNo) {
    const e = String(empNo || '').trim()
    if (!e) return ACCOUNT_STATUS.ACTIVE
    return (this._transactionSnapshot?.status || this._status).get(e) || ACCOUNT_STATUS.ACTIVE
  }

  isDisabled(empNo) {
    return this.getAccountStatus(empNo) === ACCOUNT_STATUS.DISABLED
  }

  async setAccountStatus(empNo, status, currentAdminRole) {
    if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_set_role')
    const e = String(empNo || '').trim()
    if (!e) throw codedError('invalid_role_params')
    if (status !== ACCOUNT_STATUS.ACTIVE && status !== ACCOUNT_STATUS.DISABLED) {
      throw codedError('invalid_role_params')
    }
    return this._withMutationLock(async () => {
      if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_set_role')
      if (status === ACCOUNT_STATUS.DISABLED && this._roles.get(e) === ROLES.SUPER_ADMIN
        && !this.isDisabled(e)) {
        const n = await this.countActiveByRole(ROLES.SUPER_ADMIN)
        if (n <= 1) throw codedError('last_super_admin_demote')
      }
      const prevStatus = this._status.get(e)
      this._status.set(e, status)
      this._dirty = true
      try {
        await this.flush()
      } catch (err) {
        if (prevStatus === undefined) this._status.delete(e)
        else this._status.set(e, prevStatus)
        throw err
      }
      return true
    })
  }

  // === 首次部署 bootstrap ===

  /**
   * 原子 check-and-set: 第一个登录的用户 = super_admin
   * 返回 { role, bootstrapped } bootstrapped=true 表示本次是 bootstrap
   */
  async bootstrapFirstUser(empNo) {
    return this._withMutationLock(async () => {
      if (this._roles.size === 0) {
        this._roles.set(empNo, ROLES.SUPER_ADMIN)
        this._dirty = true
        await this.flush()
        return { role: ROLES.SUPER_ADMIN, bootstrapped: true }
      }
      if (!this._roles.has(empNo)) {
        this._roles.set(empNo, ROLES.USER)
        this._dirty = true
        await this.flush()
        return { role: ROLES.USER, bootstrapped: false }
      }
      return { role: this._roles.get(empNo), bootstrapped: false }
    })
  }

  // === 角色查询 ===

  getRole(empNo) {
    if (empNo === 'administrator') return ROLES.FALLBACK_ADMIN
    return (this._transactionSnapshot?.roles || this._roles).get(empNo) || ROLES.USER
  }

  /**
   * 个人偏好：admin 级默认开启查看全部；显式 false 才关闭。
   * user 不会走到这里（resolvePermissions 里 allowToggle=false）。
   */
  isViewAllSessionsEnabled(empNo) {
    if (!empNo) return false
    const prefs = (this._transactionSnapshot?.prefs || this._prefs).get(String(empNo))
    if (prefs && Object.prototype.hasOwnProperty.call(prefs, 'viewAllSessions')) {
      return !!prefs.viewAllSessions
    }
    return true
  }

  /**
   * 设置「查看全部会话」偏好（调用方需校验 canToggleViewAllSessions）
   * @param {string} empNo
   * @param {boolean} enabled
   */
  setViewAllSessions(empNo, enabled) {
    const key = String(empNo || '').trim()
    if (!key) throw codedError('emp_no_required')
    const role = this.getRole(key)
    if (!canToggleViewAllSessions(role)) {
      throw codedError('forbidden_view_all_sessions')
    }
    const cur = { ...(this._prefs.get(key) || {}) }
    // Persist explicit true/false — deleting the key would fall back to default-on.
    cur.viewAllSessions = !!enabled
    this._prefs.set(key, cur)
    this._markDirty()
    return true
  }

  async setViewAllSessionsDurable(empNo, enabled) {
    return this._withMutationLock(async () => {
      this.setViewAllSessions(empNo, enabled)
      await this.flush()
      return true
    })
  }

  /** 角色 + 个人偏好 → 有效权限 */
  resolvePermissions(empNo, role) {
    const id = empNo != null ? String(empNo) : ''
    const r = role || this.getRole(id)
    const allowToggle = canToggleViewAllSessions(r)
    return computePermissions(r, {
      viewAllSessions: allowToggle && this.isViewAllSessionsEnabled(id),
    })
  }

  hasRole(empNo) {
    return (this._transactionSnapshot?.roles || this._roles).has(empNo)
  }

  getAll() {
    return Array.from((this._transactionSnapshot?.roles || this._roles).entries()).map(([empNo, role]) => ({ empNo, role }))
  }

  /** 角色表是否为空（用于 bootstrap） */
  isEmpty() {
    return (this._transactionSnapshot?.roles || this._roles).size === 0
  }

  /**
   * 分页 + 工号模糊搜索（上千用户场景）
   * @param {{ page?: number, pageSize?: number, q?: string }} opts
   */
  listPage(opts = {}) {
    const page = Math.max(1, Number(opts.page) || 1)
    const pageSize = Math.min(200, Math.max(1, Number(opts.pageSize) || 50))
    const q = String(opts.q || '').trim().toLowerCase()

    let rows = Array.from((this._transactionSnapshot?.roles || this._roles).entries()).map(([empNo, role]) => ({ empNo, role }))
    if (q) {
      rows = rows.filter((r) => String(r.empNo).toLowerCase().includes(q)
        || String(ROLE_LABELS[r.role] || r.role).toLowerCase().includes(q))
    }
    rows.sort((a, b) => String(a.empNo).localeCompare(String(b.empNo), 'zh'))
    const total = rows.length
    const start = (page - 1) * pageSize
    const users = rows.slice(start, start + pageSize).map(({ empNo, role }) => ({
      empNo,
      role,
      roleLabel: ROLE_LABELS[role] || role,
    }))
    return {
      users,
      total,
      page,
      pageSize,
      totalPages: Math.max(1, Math.ceil(total / pageSize)),
    }
  }

  async countByRole(role) {
    let n = 0
    for (const r of this._roles.values()) if (r === role) n++
    return n
  }

  /** A07: count only active (non-disabled) accounts with the given role. */
  async countActiveByRole(role) {
    let n = 0
    for (const [empNo, r] of this._roles) {
      if (r !== role) continue
      if (this.isDisabled(empNo)) continue
      n++
    }
    return n
  }

  // === 角色管理 (admin 级) ===

  /**
   * 设置用户角色
   * 保护性 invariant: 至少保留 1 个 active super_admin（若表中曾有）
   */
  async setRole(empNo, newRole, currentAdminRole) {
    if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) {
      throw codedError('forbidden_set_role')
    }

    // SEC-26: management API may only assign assignable roles — never fallback_admin.
    const assignable = new Set([ROLES.SUPER_ADMIN, ROLES.ADMIN, ROLES.USER])
    if (!assignable.has(newRole)) {
      throw codedError('invalid_role_params')
    }

    return this._withMutationLock(async () => {
      if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_set_role')
      const currentRole = this._roles.get(empNo)
      if (currentRole === ROLES.SUPER_ADMIN && newRole !== ROLES.SUPER_ADMIN
        && !this.isDisabled(empNo)) {
        const superAdmins = await this.countActiveByRole(ROLES.SUPER_ADMIN)
        if (superAdmins <= 1) {
          throw codedError('last_super_admin_demote')
        }
      }
      const prev = this._roles.get(empNo)
      const prevStatus = this._status.get(empNo)
      this._roles.set(empNo, newRole)
      // Re-activating via setRole clears disabled when admin assigns a role.
      if (this._status.get(empNo) === ACCOUNT_STATUS.DISABLED) {
        this._status.set(empNo, ACCOUNT_STATUS.ACTIVE)
      }
      this._dirty = true
      try {
        await this.flush()
      } catch (err) {
        if (prev === undefined) this._roles.delete(empNo)
        else this._roles.set(empNo, prev)
        // A07: roll back status as well as role on persist failure.
        if (prevStatus === undefined) this._status.delete(empNo)
        else this._status.set(empNo, prevStatus)
        throw err
      }
      return true
    })
  }

  /**
   * R12: disable account (preferred) — keeps record so open registration cannot re-add.
   * Pass { hard: true } to delete role entry entirely.
   */
  async removeUser(empNo, currentAdminRole, opts = {}) {
    if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) {
      throw codedError('forbidden_remove_user')
    }
    return this._withMutationLock(async () => {
      if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_remove_user')
      const currentRole = this._roles.get(empNo)
      if (currentRole === ROLES.SUPER_ADMIN && !this.isDisabled(empNo)) {
        const superAdmins = await this.countActiveByRole(ROLES.SUPER_ADMIN)
        if (superAdmins <= 1) {
          throw codedError('last_super_admin_delete')
        }
      }
      if (opts.hard === true) {
        const prevRole = this._roles.get(empNo)
        const prevPrefs = this._prefs.get(empNo)
        const prevStatus = this._status.get(empNo)
        this._roles.delete(empNo)
        this._prefs.delete(empNo)
        this._status.delete(empNo)
        this._dirty = true
        try {
          await this.flush()
        } catch (err) {
          if (prevRole !== undefined) this._roles.set(empNo, prevRole)
          if (prevPrefs !== undefined) this._prefs.set(empNo, prevPrefs)
          if (prevStatus !== undefined) this._status.set(empNo, prevStatus)
          throw err
        }
      } else {
        const key = String(empNo)
        const prevStatus = this._status.get(key)
        this._status.set(key, ACCOUNT_STATUS.DISABLED)
        this._dirty = true
        try {
          await this.flush()
        } catch (err) {
          if (prevStatus === undefined) this._status.delete(key)
          else this._status.set(key, prevStatus)
          throw err
        }
      }
      return true
    })
  }

  /**
   * 确保用户存在 (如果不存在设为 user)；disabled 账号不会被自动复活。
   * F03: await flush before success — no silent delayed-only persist.
   */
  async ensureUser(empNo, currentAdminRole) {
    if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) {
      throw codedError('forbidden_add_user')
    }
    if (this.isDisabled(empNo)) {
      throw codedError('account_disabled')
    }
    return this._withMutationLock(async () => {
      if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_add_user')
      if (this.isDisabled(empNo)) throw codedError('account_disabled')
      if (!this._roles.has(empNo)) {
        this._roles.set(empNo, ROLES.USER)
        this._status.set(String(empNo), ACCOUNT_STATUS.ACTIVE)
        this._dirty = true
        try {
          await this.flush()
        } catch (err) {
          this._roles.delete(empNo)
          this._status.delete(String(empNo))
          throw err
        }
      }
      return true
    })
  }

  // === Fallback Administrator ===

  _ensureCommittedFallback() {
    if (!this._committedFallback) {
      this._committedFallback = {
        hash: this._fallbackPasswordHash,
        needs: this._fallbackNeedsRehash,
        ver: this._fallbackCredVersion || 0,
      }
    }
  }

  _restoreCommittedFallback() {
    this._ensureCommittedFallback()
    this._fallbackPasswordHash = this._committedFallback.hash
    this._fallbackNeedsRehash = this._committedFallback.needs
    this._fallbackCredVersion = this._committedFallback.ver
  }

  _captureCommittedFallback() {
    this._committedFallback = {
      hash: this._fallbackPasswordHash,
      needs: this._fallbackNeedsRehash,
      ver: this._fallbackCredVersion || 0,
    }
  }

  /**
   * D05/D06/F03: persist against last-committed snapshot.
   * Failed writes restore the last successful commit (not a concurrent peer's
   * uncommitted value), including credVersion.
   */
  async setFallbackPassword(password, currentAdminRole) {
    if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) {
      throw codedError('forbidden_set_fallback')
    }
    if (String(password) === 'Admin@123') {
      throw codedError('password_too_common')
    }
    if (typeof password !== 'string' || password.length < 10) {
      throw codedError('password_too_short')
    }
    if (Buffer.byteLength(password) > 1024) throw codedError('password_invalid')
    return this._withMutationLock(async () => {
      if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_set_fallback')
      const newHash = await hashPasswordAsync(password)
      this._fallbackPasswordHash = newHash
      this._fallbackNeedsRehash = false
      this._fallbackCredVersion++
      this._dirty = true
      await this.flush()
      this._captureCommittedFallback()
      return true
    })
  }

  async clearFallbackPassword(currentAdminRole) {
    if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) {
      throw codedError('forbidden_clear_fallback')
    }
    return this._withMutationLock(async () => {
      if (!isAdminClass(typeof currentAdminRole === 'function' ? currentAdminRole() : currentAdminRole)) throw codedError('forbidden_clear_fallback')
      this._fallbackPasswordHash = null
      this._fallbackNeedsRehash = false
      this._fallbackCredVersion++
      this._dirty = true
      await this.flush()
      this._captureCommittedFallback()
      return true
    })
  }

  /** Auth material version for password-fallback sessions (F02). */
  getFallbackCredVersion() {
    return this._transactionSnapshot?.ver ?? this._fallbackCredVersion ?? 0
  }

  isFallbackEnabled() {
    return (this._transactionSnapshot ? this._transactionSnapshot.hash : this._fallbackPasswordHash) !== null
  }

  /** Runtime path: asynchronous bounded KDF and recheck after a concurrent rotation. */
  async verifyFallbackAsync(password, ip) {
    if (typeof password !== 'string' || Buffer.byteLength(password) > 1024) return false
    const hash = this._transactionSnapshot ? this._transactionSnapshot.hash : this._fallbackPasswordHash
    const version = this.getFallbackCredVersion()
    if (!hash) return false
    const now = Date.now()
    for (const [key, value] of this._fallbackRateLimit) {
      if (value.resetAt <= now) this._fallbackRateLimit.delete(key)
    }
    let bucket = this._fallbackRateLimit.get(ip)
    if (!bucket) {
      if (this._fallbackRateLimit.size >= 5000) return false
      this._fallbackRateLimit.set(ip, bucket = { count: 0, resetAt: now + 60_000 })
    }
    if (++bucket.count > 5) return false
    const ok = String(hash).startsWith('scrypt$')
      ? await verifyScryptAsync(password, hash) : verifyPasswordHash(password, hash)
    if (!ok) return false
    // Serialize the final check with all durable credential changes.
    return this._withMutationLock(async () => {
      if (this._fallbackPasswordHash !== hash || this._fallbackCredVersion !== version) return false
      if (!String(hash).startsWith('scrypt$')) {
        this._fallbackPasswordHash = await hashPasswordAsync(password)
        this._fallbackNeedsRehash = false
        this._dirty = true
        await this.flush()
        this._captureCommittedFallback()
      }
      return true
    })
  }

  /**
   * 验证 fallback 密码 + rate limit
   * @returns {boolean}
   */
  verifyFallback(password, ip) {
    if (!this._fallbackPasswordHash) return false
    const now = Date.now()

    // rate limit: 5 tries per minute per IP
    let bucket = this._fallbackRateLimit.get(ip)
    if (!bucket || now > bucket.resetAt) {
      bucket = { count: 0, resetAt: now + 60_000 }
      this._fallbackRateLimit.set(ip, bucket)
    }
    bucket.count++
    if (bucket.count > 5) {
      return false // rate limited
    }

    const ok = verifyPasswordHash(password, this._fallbackPasswordHash)
    if (ok && (this._fallbackNeedsRehash || !String(this._fallbackPasswordHash).startsWith('scrypt$'))) {
      try {
        this._fallbackPasswordHash = hashPasswordScrypt(password)
        this._fallbackNeedsRehash = false
        this._markDirty()
      } catch { /* keep legacy until next save */ }
    }
    return ok
  }
}

export { ACCOUNT_STATUS, hashPasswordScrypt, verifyPasswordHash, LEGACY_DEFAULT_SHA256 }
