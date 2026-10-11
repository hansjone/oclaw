import { randomBytes, scrypt, timingSafeEqual } from 'node:crypto'

// A shared bound across password login, rotation and sealed-box unlock. Reject
// overload instead of keeping unbounded request/password buffers in memory.
const MAX_RUNNING = 2
const MAX_WAITING = 8
let running = 0
const waiting = []

export async function derivePasswordKey(password, salt, length = 32) {
  if (typeof password !== 'string' || Buffer.byteLength(password) > 1024) {
    throw Object.assign(new Error('password_invalid'), { code: 'password_invalid' })
  }
  if (running >= MAX_RUNNING) {
    if (waiting.length >= MAX_WAITING) {
      throw Object.assign(new Error('kdf_busy'), { code: 'kdf_busy' })
    }
    await new Promise(resolve => waiting.push(resolve))
  } else running++
  try {
    return await new Promise((resolve, reject) => {
      scrypt(password, salt, length, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 },
        (err, key) => err ? reject(err) : resolve(key))
    })
  } finally {
    const next = waiting.shift()
    if (next) next()
    else running--
  }
}

export async function hashPasswordAsync(password) {
  const salt = randomBytes(16)
  const key = await derivePasswordKey(password, salt)
  return `scrypt$16384$8$1$${salt.toString('base64url')}$${key.toString('base64url')}`
}

export async function verifyScryptAsync(password, stored) {
  const parts = String(stored).split('$')
  // Never accept attacker-controlled KDF work factors or output sizes.
  if (parts.length !== 6 || parts.slice(0, 4).join('$') !== 'scrypt$16384$8$1') return false
  const salt = Buffer.from(parts[4], 'base64url')
  const expected = Buffer.from(parts[5], 'base64url')
  if (salt.length !== 16 || expected.length !== 32) return false
  const actual = await derivePasswordKey(password, salt)
  return timingSafeEqual(actual, expected)
}
