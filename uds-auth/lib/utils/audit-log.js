/**
 * SEC-25: structured security audit events (no secrets).
 */
import { randomBytes } from 'node:crypto'

const SECRET_KEYS = /^(token|password|passphrase|authorization|cookie|authvalue|sso|bearer|secret|key)$/i

/**
 * @param {unknown} value
 * @returns {unknown}
 */
export function redactValue(value) {
  if (value == null) return value
  if (typeof value === 'string') {
    if (value.length > 64) return value.slice(0, 8) + '…(' + value.length + ')'
    return value
  }
  if (Array.isArray(value)) return value.map(redactValue)
  if (typeof value === 'object') {
    const out = {}
    for (const [k, v] of Object.entries(value)) {
      if (SECRET_KEYS.test(k) || /token|password|cookie|secret|auth/i.test(k)) {
        out[k] = '[redacted]'
      } else {
        out[k] = redactValue(v)
      }
    }
    return out
  }
  return value
}

/**
 * @param {object} event
 * @param {{ logger?: Console }} [opts]
 */
export function audit(event, opts = {}) {
  const logger = opts.logger || console
  const row = {
    ts: new Date().toISOString(),
    type: 'uds-auth.audit',
    correlationId: event.correlationId || randomBytes(8).toString('hex'),
    action: event.action,
    decision: event.decision || 'info',
    reasonCode: event.reasonCode || null,
    actor: event.actor || null,
    target: event.target || null,
    resource: event.resource || null,
    service: event.service || 'uds-auth',
    meta: event.meta ? redactValue(event.meta) : undefined,
  }
  const line = JSON.stringify(row)
  if (event.decision === 'deny' || event.decision === 'error') {
    logger.warn?.(line)
  } else {
    logger.info?.(line)
  }
  return row
}
