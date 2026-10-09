/**
 * Last verified browser identity (bridge or cookie).
 * Desktop mux follow/history often runs with empty ALS; fall back here after
 * a successful /uds-auth HTTP auth or WS upgrade bind.
 */

/** @type {object|null} */
let lastBrowserIdentity = null

export function rememberBrowserIdentity(identity) {
  const emp = identity?.empNo || identity?.userContext?.empNo
  if (!emp) return
  lastBrowserIdentity = identity
}

export function clearBrowserIdentity() {
  lastBrowserIdentity = null
}

export function peekBrowserIdentity() {
  return lastBrowserIdentity
}
