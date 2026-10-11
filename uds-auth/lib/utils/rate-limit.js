/**
 * SEC-23: simple in-memory rate limiter with bucket cleanup.
 * Keyed by real socket address (not XFF).
 */

export class RateLimiter {
  /**
   * @param {{ windowMs?: number, max?: number, maxBuckets?: number }} [opts]
   */
  constructor(opts = {}) {
    this._windowMs = opts.windowMs ?? 60_000
    this._max = opts.max ?? 30
    this._maxBuckets = opts.maxBuckets ?? 10_000
    /** @type {Map<string, { count: number, resetAt: number }>} */
    this._buckets = new Map()
    this._sweepTimer = setInterval(() => this._sweep(), Math.max(this._windowMs, 30_000))
    if (typeof this._sweepTimer.unref === 'function') this._sweepTimer.unref()
  }

  _sweep() {
    const now = Date.now()
    for (const [k, b] of this._buckets) {
      if (now > b.resetAt) this._buckets.delete(k)
    }
  }

  /**
   * @param {string} key
   * @returns {boolean} true if allowed
   */
  allow(key) {
    const id = String(key || 'unknown')
    const now = Date.now()
    let bucket = this._buckets.get(id)
    if (!bucket || now > bucket.resetAt) {
      if (this._buckets.size >= this._maxBuckets) this._sweep()
      if (this._buckets.size >= this._maxBuckets) {
        // Evict oldest-ish entry
        const first = this._buckets.keys().next().value
        if (first != null) this._buckets.delete(first)
      }
      bucket = { count: 0, resetAt: now + this._windowMs }
      this._buckets.set(id, bucket)
    }
    bucket.count++
    return bucket.count <= this._max
  }

  dispose() {
    clearInterval(this._sweepTimer)
    this._buckets.clear()
  }
}

export function clientKey(req) {
  const ra = req?.socket?.remoteAddress || 'unknown'
  return String(ra).replace(/^::ffff:/i, '')
}
