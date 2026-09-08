/**
 * uds-auth 角色存储 + 权限管理
 * 
 * 角色:
 *   super_admin  所有权限 + 用户管理
 *   admin         设置权限 + 仅看自己会话
 *   user          仅看自己会话，无设置
 *
 * 持久化: roles.json (单实例文件) + MemoryStore 同步
 */
import { createHash, randomBytes } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

export const ROLES = {
  SUPER_ADMIN: 'super_admin',
  ADMIN: 'admin',
  USER: 'user',
  FALLBACK_ADMIN: 'fallback_admin', // 特殊，UAC 挂了时用，等同 super_admin 权限
}

export const ROLE_LABELS = {
  super_admin: '超级管理员',
  admin: '管理员',
  user: '普通用户',
  fallback_admin: '兜底管理员',
}

/** 计算角色权限 (纯函数) */
export function computePermissions(role) {
  switch (role) {
    case ROLES.SUPER_ADMIN:
      return {
        canManageUsers: true,
        canAccessSettings: true,
        canViewAllSessions: true,
        canCreateWorkspace: true,
      }
    case ROLES.FALLBACK_ADMIN:
      return {
        canManageUsers: true,
        canAccessSettings: true,
        canViewAllSessions: true,
        canCreateWorkspace: true,
      }
    case ROLES.ADMIN:
      return {
        canManageUsers: false,
        canAccessSettings: true,
        canViewAllSessions: false,
        canCreateWorkspace: false,
      }
    default: // user / undefined
      return {
        canManageUsers: false,
        canAccessSettings: false,
        canViewAllSessions: false,
        canCreateWorkspace: false,
      }
  }
}

function hashPassword(password) {
  return createHash('sha256').update(password).digest('hex')
}

/** 初始部署默认兜底密码（扫码不可用时用）；可在设置里改密或关闭。 */
export const DEFAULT_FALLBACK_PASSWORD = 'Admin@123'
export const DEFAULT_FALLBACK_USERNAME = 'administrator'

/**
 * RolesStore — 角色存储
 * 内存 Map + 可选 JSON 文件持久化
 *
 * fallback admin: 默认启用，密码 Admin@123；roles.json 显式 null 表示已关闭。
 *   登录路径: POST /uds-auth/api/fallback/login { username, password }
 */
export class RolesStore {
  constructor(options = {}) {
    this._roles = new Map()              // empNo → role
    this._firstBootLock = Promise.resolve()
    this._rolesFile = options.rolesFile ? resolve(options.rolesFile) : null
    this._fallbackPasswordHash = null     // SHA-256 hex，null = 未启用
    this._fallbackRateLimit = new Map()   // ip → { count, resetAt }
    this._dirty = false
    this._saveTimer = null
  }

  _ensureDefaultFallback() {
    if (this._fallbackPasswordHash) return
    this._fallbackPasswordHash = hashPassword(DEFAULT_FALLBACK_PASSWORD)
    this._markDirty()
    console.info(
      '[uds-auth] fallback_admin enabled by default'
      + ` (user=${DEFAULT_FALLBACK_USERNAME}, change password in settings)`,
    )
  }

  // === 持久化 ===

  async init() {
    let loadedHash = undefined // undefined = missing / new file; null = explicitly cleared
    if (this._rolesFile) {
      try {
        const raw = await readFile(this._rolesFile, 'utf-8')
        const data = JSON.parse(raw)
        for (const [empNo, role] of Object.entries(data.roles || {})) {
          this._roles.set(empNo, role)
        }
        if (Object.prototype.hasOwnProperty.call(data, 'fallbackPasswordHash')) {
          loadedHash = data.fallbackPasswordHash || null
          if (loadedHash) this._fallbackPasswordHash = loadedHash
        }
      } catch (err) {
        if (err.code === 'ENOENT') {
          // 首次启动，文件不存在 — 走默认兜底
        } else {
          console.warn('[uds-auth:RolesStore] Failed to load roles file:', err.message)
        }
      }
    }
    // 无持久化哈希（新部署或旧文件未写该字段）→ 默认开启；显式 null 表示超管已关闭
    if (loadedHash === undefined && !this._fallbackPasswordHash) {
      this._ensureDefaultFallback()
    }
  }

  _markDirty() {
    this._dirty = true
    if (this._saveTimer) return
    this._saveTimer = setTimeout(() => this._save(), 2000)
  }

  async _save() {
    this._saveTimer = null
    if (!this._dirty || !this._rolesFile) return
    this._dirty = false
    try {
      const data = {
        roles: Object.fromEntries(this._roles),
        fallbackPasswordHash: this._fallbackPasswordHash,
        savedAt: new Date().toISOString(),
      }
      await mkdir(dirname(this._rolesFile), { recursive: true })
      await writeFile(this._rolesFile, JSON.stringify(data, null, 2), 'utf-8')
    } catch (err) {
      console.warn('[uds-auth:RolesStore] Failed to save roles file:', err.message)
    }
  }

  // === 首次部署 bootstrap ===

  /**
   * 原子 check-and-set: 第一个登录的用户 = super_admin
   * 返回 { role, bootstrapped } bootstrapped=true 表示本次是 bootstrap
   */
  async bootstrapFirstUser(empNo) {
    // 用锁保证原子性
    this._firstBootLock = this._firstBootLock.then(async () => {
      if (this._roles.size === 0) {
        this._roles.set(empNo, ROLES.SUPER_ADMIN)
        this._markDirty()
        return { role: ROLES.SUPER_ADMIN, bootstrapped: true }
      }
      if (!this._roles.has(empNo)) {
        this._roles.set(empNo, ROLES.USER)
        this._markDirty()
        return { role: ROLES.USER, bootstrapped: false }
      }
      return { role: this._roles.get(empNo), bootstrapped: false }
    })
    return this._firstBootLock
  }

  // === 角色查询 ===

  getRole(empNo) {
    if (empNo === 'administrator') return ROLES.FALLBACK_ADMIN
    return this._roles.get(empNo) || ROLES.USER
  }

  hasRole(empNo) {
    return this._roles.has(empNo)
  }

  getAll() {
    return Array.from(this._roles.entries()).map(([empNo, role]) => ({ empNo, role }))
  }

  /** 角色表是否为空（用于 bootstrap） */
  isEmpty() {
    return this._roles.size === 0
  }

  /**
   * 分页 + 工号模糊搜索（上千用户场景）
   * @param {{ page?: number, pageSize?: number, q?: string }} opts
   */
  listPage(opts = {}) {
    const page = Math.max(1, Number(opts.page) || 1)
    const pageSize = Math.min(200, Math.max(1, Number(opts.pageSize) || 50))
    const q = String(opts.q || '').trim().toLowerCase()

    let rows = Array.from(this._roles.entries()).map(([empNo, role]) => ({ empNo, role }))
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

  // === 角色管理 (super_admin only) ===

  /**
   * 设置用户角色
   * 保护性 invariant: 至少保留 1 个 super_admin
   */
  async setRole(empNo, newRole, currentAdminRole) {
    if (currentAdminRole !== ROLES.SUPER_ADMIN) {
      throw new Error('只有超级管理员可以修改角色')
    }

    // invariant: 不能让系统变成 0 个 super_admin
    const currentRole = this._roles.get(empNo)
    if (currentRole === ROLES.SUPER_ADMIN && newRole !== ROLES.SUPER_ADMIN) {
      const superAdmins = await this.countByRole(ROLES.SUPER_ADMIN)
      if (superAdmins <= 1) {
        throw new Error('系统至少需要 1 个超级管理员，不能降级最后一个')
      }
    }

    this._roles.set(empNo, newRole)
    this._markDirty()
    return true
  }

  /** 删除用户 */
  async removeUser(empNo, currentAdminRole) {
    if (currentAdminRole !== ROLES.SUPER_ADMIN) {
      throw new Error('只有超级管理员可以删除用户')
    }
    const currentRole = this._roles.get(empNo)
    if (currentRole === ROLES.SUPER_ADMIN) {
      const superAdmins = await this.countByRole(ROLES.SUPER_ADMIN)
      if (superAdmins <= 1) {
        throw new Error('系统至少需要 1 个超级管理员，不能删除最后一个')
      }
    }
    this._roles.delete(empNo)
    this._markDirty()
    return true
  }

  /** 确保用户存在 (如果不存在设为 user) */
  ensureUser(empNo, currentAdminRole) {
    if (currentAdminRole !== ROLES.SUPER_ADMIN) {
      throw new Error('只有超级管理员可以添加用户')
    }
    if (!this._roles.has(empNo)) {
      this._roles.set(empNo, ROLES.USER)
      this._markDirty()
    }
    return true
  }

  // === Fallback Administrator ===

  setFallbackPassword(password, currentAdminRole) {
    if (currentAdminRole !== ROLES.SUPER_ADMIN && currentAdminRole !== ROLES.FALLBACK_ADMIN) {
      throw new Error('只有超级管理员可以设置兜底管理员密码')
    }
    if (!password || password.length < 6) {
      throw new Error('密码至少 6 位')
    }
    this._fallbackPasswordHash = hashPassword(password)
    this._markDirty()
    return true
  }

  clearFallbackPassword(currentAdminRole) {
    if (currentAdminRole !== ROLES.SUPER_ADMIN && currentAdminRole !== ROLES.FALLBACK_ADMIN) {
      throw new Error('只有超级管理员可以清除兜底管理员密码')
    }
    this._fallbackPasswordHash = null
    this._markDirty()
    return true
  }

  isFallbackEnabled() {
    return this._fallbackPasswordHash !== null
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

    return hashPassword(password) === this._fallbackPasswordHash
  }
}
