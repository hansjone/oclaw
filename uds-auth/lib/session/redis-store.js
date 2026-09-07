import { SessionStore } from './store.js'

/**
 * Redis-backed session store (for production / 多实例)
 * Requires 'redis' package: npm install redis
 * Key: uds-session:{empNo}
 */
export class RedisStore extends SessionStore {
  constructor(redisClient) {
    super()
    if (!redisClient) throw new Error('Redis client is required')
    this._client = redisClient
  }

  _key(empNo) { return `uds-session:${empNo}` }

  async get(empNo) {
    const data = await this._client.get(this._key(empNo))
    return data ? JSON.parse(data) : null
  }

  async set(empNo, userData) {
    await this._client.set(this._key(empNo), JSON.stringify(userData))
  }

  async setex(empNo, seconds, userData) {
    await this._client.setEx(this._key(empNo), seconds, JSON.stringify(userData))
  }

  async delete(empNo) {
    await this._client.del(this._key(empNo))
  }

  async has(empNo) {
    return (await this._client.exists(this._key(empNo))) === 1
  }

  async clear() {
    const keys = await this._client.keys('uds-session:*')
    if (keys.length > 0) await this._client.del(keys)
  }

  async keys() {
    const all = await this._client.keys('uds-session:*')
    return all.map(k => k.replace(/^uds-session:/, ''))
  }
}
