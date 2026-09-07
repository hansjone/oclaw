import { AsyncLocalStorage } from 'node:async_hooks'

/**
 * Async local storage for user context
 * Ensures user context is isolated per request even in concurrent scenarios
 */
const userContextStorage = new AsyncLocalStorage()

/**
 * Get the current user context from async local storage
 * @returns {object|undefined} User context object or undefined
 */
export function getUserContext() {
  return userContextStorage.getStore()
}

/**
 * Execute a function with a specific user context
 * @param {object} userContext - User context object
 * @param {Function} fn - Async function to execute
 * @returns {Promise<any>} Result of the function
 */
export async function withUserContext(userContext, fn) {
  return userContextStorage.run(userContext, fn)
}

/**
 * Decorator/helper for injecting user context into request handlers
 * @param {Function} handler - Request handler function
 * @returns {Function} Wrapped handler
 */
export function withInjectedUserContext(handler) {
  return async function(ctx, ...args) {
    const userContext = ctx.userContext || null
    return userContextStorage.run(userContext, () => handler(ctx, ...args))
  }
}
