/**
 * Deprecated global last-user cache (SEC-06).
 * Kept as no-ops so older imports do not crash; never restores a principal.
 */

export function rememberBrowserIdentity(_identity) {
  /* intentionally no-op — connection-bound identity only */
}

export function clearBrowserIdentity() {
  /* intentionally no-op */
}

export function peekBrowserIdentity() {
  return null
}
