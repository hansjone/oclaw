import { MemoryStore } from './memory-store.js'
import { RedisStore } from './redis-store.js'

/**
 * Factory function to create appropriate session store based on config
 * @param {object} config - Session configuration
 * @returns {Promise<SessionStore>}
 */
export async function createSessionStore(config) {
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
      return new MemoryStore()
    }
  }
  
  // Default to memory store
  return new MemoryStore()
}
