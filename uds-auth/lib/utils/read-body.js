/**
 * SEC-23: bounded body readers.
 */
export const DEFAULT_MAX_BODY = 256 * 1024
export const MAX_QR_PROXY_BODY = 64 * 1024
export const MAX_QR_DATA_LEN = 2048

/**
 * @param {import('node:http').IncomingMessage} req
 * @param {{ maxBytes?: number }} [opts]
 * @returns {Promise<string>}
 */
export async function readBodyLimited(req, opts = {}) {
  const maxBytes = opts.maxBytes ?? DEFAULT_MAX_BODY
  const chunks = []
  let total = 0
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
    total += buf.length
    if (total > maxBytes) {
      const err = new Error('payload_too_large')
      err.code = 'payload_too_large'
      err.statusCode = 413
      // Drain remaining to free the socket (best-effort).
      try { req.resume() } catch { /* ignore */ }
      throw err
    }
    chunks.push(buf)
  }
  return Buffer.concat(chunks).toString('utf8')
}

/**
 * @param {import('node:http').IncomingMessage} req
 * @param {{ maxBytes?: number }} [opts]
 * @returns {Promise<object>}
 */
export async function readJsonBodyLimited(req, opts = {}) {
  const raw = await readBodyLimited(req, opts)
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    const err = new Error('invalid_json')
    err.code = 'invalid_json'
    err.statusCode = 400
    throw err
  }
}
