/**
 * Map a Node network/TLS error to a stable, user-actionable api error code
 * (see `err.upstream_*` in i18n.js). Keeps raw errno out of API responses.
 */
const DNS_CODES = new Set(['ENOTFOUND', 'EAI_AGAIN', 'EAI_FAIL', 'EAI_NODATA'])
const TIMEOUT_CODES = new Set(['ETIMEDOUT', 'ESOCKETTIMEDOUT', 'ECONNABORTED'])
const UNREACHABLE_CODES = new Set([
  'ECONNREFUSED', 'ECONNRESET', 'EHOSTUNREACH', 'ENETUNREACH', 'EPIPE', 'EADDRNOTAVAIL',
])
const CERT_CODES = new Set([
  'UNABLE_TO_VERIFY_LEAF_SIGNATURE',
  'UNABLE_TO_GET_ISSUER_CERT',
  'UNABLE_TO_GET_ISSUER_CERT_LOCALLY',
  'SELF_SIGNED_CERT_IN_CHAIN',
  'DEPTH_ZERO_SELF_SIGNED_CERT',
  'CERT_HAS_EXPIRED',
  'CERT_NOT_YET_VALID',
  'CERT_UNTRUSTED',
  'ERR_TLS_CERT_ALTNAME_INVALID',
  'HOSTNAME_MISMATCH',
])

/**
 * @param {{ code?: string, message?: string } | null | undefined} err
 * @returns {'upstream_dns' | 'upstream_timeout' | 'upstream_unreachable' | 'upstream_cert' | 'upstream_error'}
 */
export function classifyNetworkError(err) {
  const code = String(err?.code || '')
  const msg = String(err?.message || '')
  if (CERT_CODES.has(code) || /certificate|self[- ]signed/i.test(msg)) return 'upstream_cert'
  if (DNS_CODES.has(code)) return 'upstream_dns'
  if (TIMEOUT_CODES.has(code) || /timeout|timed out/i.test(msg)) return 'upstream_timeout'
  if (UNREACHABLE_CODES.has(code) || /socket hang up/i.test(msg)) return 'upstream_unreachable'
  return 'upstream_error'
}

/** Host for diagnostics only; never throws. */
export function hostOfUrl(raw) {
  try { return new URL(String(raw)).hostname } catch { return '' }
}
