import { MemoryStore } from './memory-store.js'
import { RedisStore } from './redis-store.js'

/**
 * Factory function to create appropriate session store based on config
 * @param {object} config - Session configuration
 * @param {{ file?: string, dataDir?: string, logger?: any }} [persist] - MemoryStore disk persistence
 * @returns {Promise<SessionStore>}
 */
export async function createSessionStore(config, persist = {}) {
  const { storeType, redisUrl } = config
  
  if (storeType === 'redis') {
    try {
      const { createClient } = await import('redis')
      const client = createClient({ url: redisUrl })
      await client.connect()
      return new RedisStore(client)
    } catch (err) {
      console.error('[uds-auth] Failed to connect to Redis:', err.message)
      console.warn('[uds-auth] Falling back to MemoryStore')
      const store = new MemoryStore(persist)
      await store.init()
      return store
    }
  }
  
  // Default to memory store (persisted to the profile data dir when configured)
  const store = new MemoryStore(persist)
  await store.init()
  return store
}
