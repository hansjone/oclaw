import { SessionStore } from './store.js'

/**
 * In-memory session store — 单索引 empNo → userData
 * 一个工号 = 一个会话，多终端同工号共享同一条目。
 */
export class MemoryStore extends SessionStore {
  constructor() {
    super()
    this._sessions = new Map() // Map<empNo, { userData, expiresAt }>
    this._timers = new Map()    // Map<empNo, Timeout>
  }

  async get(empNo) {
    const session = this._sessions.get(empNo)
    if (!session) return null
    if (session.expiresAt && Date.now() > session.expiresAt) {
      await this.delete(empNo)
      return null
    }
    return { ...session.userData }
  }

  async set(empNo, userData) {
    this._sessions.set(empNo, { userData })
  }

  async setex(empNo, seconds, userData) {
    this._sessions.set(empNo, { userData, expiresAt: Date.now() + seconds * 1000 })
    if (this._timers.has(empNo)) clearTimeout(this._timers.get(empNo))
    this._timers.set(empNo, setTimeout(() => this._sessions.delete(empNo), seconds * 1000))
  }

  async delete(empNo) {
    if (this._timers.has(empNo)) {
      clearTimeout(this._timers.get(empNo))
      this._timers.delete(empNo)
    }
    this._sessions.delete(empNo)
  }

  async has(empNo) {
    const session = this._sessions.get(empNo)
    if (!session) return false
    if (session.expiresAt && Date.now() > session.expiresAt) {
      await this.delete(empNo)
      return false
    }
    return true
  }

  async clear() {
    for (const t of this._timers.values()) clearTimeout(t)
    this._timers.clear()
    this._sessions.clear()
  }

  async keys() {
    return Array.from(this._sessions.keys())
  }
}
