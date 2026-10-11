import { createHash, randomBytes, timingSafeEqual } from 'node:crypto'
const digest = value => createHash('sha256').update(String(value || '')).digest()

export class QrChallengeStore {
  constructor({ ttlMs = 120_000, maxEntries = 5000 } = {}) {
    this.rows = new Map()
    this.ttlMs = ttlMs
    this.maxEntries = maxEntries
  }
  create({ loginSystemCode, originSystemCode }) {
    for (const [key, row] of this.rows) if (row.expiresAt <= Date.now()) this.rows.delete(key)
    if (this.rows.size >= this.maxEntries) throw Object.assign(new Error('qr_capacity'), { code: 'qr_capacity' })
    const qrCodeKey = randomBytes(16).toString('hex')
    const qrCodeValue = randomBytes(16).toString('hex')
    // The QR contains only public scan coordinates, never the polling browser proof.
    const browserBinding = randomBytes(32).toString('hex')
    const expiresAt = Date.now() + this.ttlMs
    this.rows.set(qrCodeKey, { qrCodeValue, bindingHash: digest(browserBinding), expiresAt,
      loginSystemCode, originSystemCode, consumed: false })
    return { qrCodeKey, qrCodeValue, browserBinding, expiresAt, loginSystemCode, originSystemCode,
      qrCodeStr: `TwoDIMAuth:${qrCodeKey}:${qrCodeValue}` }
  }
  peek(key, value, binding) {
    const row = this.rows.get(String(key || ''))
    if (!row) return { ok: false, reason: 'qr_unknown' }
    if (row.expiresAt <= Date.now()) { this.rows.delete(String(key)); return { ok: false, reason: 'qr_expired' } }
    if (row.consumed) return { ok: false, reason: 'qr_replay' }
    if (!timingSafeEqual(digest(value), digest(row.qrCodeValue))) return { ok: false, reason: 'qr_mismatch' }
    if (typeof binding !== 'string' || !/^[a-f0-9]{64}$/.test(binding)
      || !timingSafeEqual(digest(binding), row.bindingHash)) return { ok: false, reason: 'qr_binding_required' }
    return { ok: true, row }
  }
  consume(key, value, binding) {
    const result = this.peek(key, value, binding)
    if (!result.ok) return result
    result.row.consumed = true
    return { ok: true }
  }
}

/** Known UAC contract: outer code + bo.code and credentials in other. */
export function qrLoginCredentials(payload) {
  if (String(payload?.code?.code ?? payload?.code) !== '0000' || String(payload?.bo?.code) !== '0000') return null
  const empNo = String(payload?.other?.account || payload?.other?.empNo || '').trim()
  const token = String(payload?.other?.token || payload?.other?.authValue || '').trim()
  if (!empNo || !token || empNo.length > 128 || token.length > 16384) return null
  return { empNo, token }
}
