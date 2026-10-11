/**
 * SEC-17 / R11: encrypt upstream secrets at rest (AES-256-GCM).
 * Key from UDS_AUTH_SECRET_KEY (64 hex) or plugin-local key file.
 * Invalid env / corrupt key file fail closed — never silently replace.
 */
import { createCipheriv, createDecipheriv, randomBytes, createHash, scryptSync } from 'node:crypto'
import { readFile, writeFile, mkdir, chmod, access } from 'node:fs/promises'
import { constants as fsConstants } from 'node:fs'
import { dirname, join } from 'node:path'

const MAGIC = 'uds-secret-v1'

function keyFilePath(dataDir) {
  return join(dataDir, '.uds-auth-secret-key')
}

/**
 * @param {string} dataDir plugin data directory
 * @param {{ hasEncryptedData?: boolean }} [opts]
 * @returns {Promise<Buffer>} 32-byte key
 */
export async function loadOrCreateSecretKey(dataDir, opts = {}) {
  const env = String(process.env.UDS_AUTH_SECRET_KEY || '').trim()
  if (env) {
    if (!/^[0-9a-fA-F]{64}$/.test(env)) {
      const err = new Error('invalid_secret_key_env')
      err.code = 'invalid_secret_key_env'
      throw err
    }
    return Buffer.from(env, 'hex')
  }

  const keyFile = keyFilePath(dataDir)
  let fileExists = false
  try {
    await access(keyFile, fsConstants.F_OK)
    fileExists = true
  } catch { /* absent */ }

  if (fileExists) {
    let raw
    try {
      raw = (await readFile(keyFile, 'utf-8')).trim()
    } catch (err) {
      const e = new Error('secret_key_unreadable')
      e.code = 'secret_key_unreadable'
      e.cause = err
      throw e
    }
    if (!/^[0-9a-fA-F]{64}$/.test(raw)) {
      const e = new Error('secret_key_corrupt')
      e.code = 'secret_key_corrupt'
      throw e
    }
    return Buffer.from(raw, 'hex')
  }

  // Only mint a new key on a confirmed empty deployment (no prior key file).
  if (opts.hasEncryptedData) {
    const e = new Error('secret_key_missing')
    e.code = 'secret_key_missing'
    throw e
  }

  const key = randomBytes(32)
  await mkdir(dirname(keyFile), { recursive: true })
  // Exclusive create — avoid concurrent overwrite races.
  const { open } = await import('node:fs/promises')
  let fh
  try {
    fh = await open(keyFile, 'wx')
    await fh.writeFile(key.toString('hex') + '\n', { encoding: 'utf8' })
  } catch (err) {
    if (err.code === 'EEXIST') {
      const raw = (await readFile(keyFile, 'utf-8')).trim()
      if (/^[0-9a-fA-F]{64}$/.test(raw)) return Buffer.from(raw, 'hex')
      const e = new Error('secret_key_corrupt')
      e.code = 'secret_key_corrupt'
      throw e
    }
    throw err
  } finally {
    try { await fh?.close() } catch { /* ignore */ }
  }
  try { await chmod(keyFile, 0o600) } catch { /* win */ }
  return key
}

/**
 * @param {Buffer} key
 * @param {string} plaintext
 * @returns {string} sealed blob
 */
export function sealSecret(key, plaintext) {
  const iv = randomBytes(12)
  const cipher = createCipheriv('aes-256-gcm', key, iv)
  const enc = Buffer.concat([cipher.update(String(plaintext), 'utf8'), cipher.final()])
  const tag = cipher.getAuthTag()
  return [
    MAGIC,
    iv.toString('base64url'),
    tag.toString('base64url'),
    enc.toString('base64url'),
  ].join('.')
}

/**
 * @param {Buffer} key
 * @param {string} blob
 * @returns {string|null}
 */
export function openSecret(key, blob) {
  const parts = String(blob || '').split('.')
  if (parts.length !== 4 || parts[0] !== MAGIC) return null
  try {
    const iv = Buffer.from(parts[1], 'base64url')
    const tag = Buffer.from(parts[2], 'base64url')
    const enc = Buffer.from(parts[3], 'base64url')
    const decipher = createDecipheriv('aes-256-gcm', key, iv)
    decipher.setAuthTag(tag)
    return Buffer.concat([decipher.update(enc), decipher.final()]).toString('utf8')
  } catch {
    return null
  }
}

/** Stable fingerprint for logs — never the secret itself. */
export function secretFingerprint(value) {
  return createHash('sha256').update(String(value)).digest('hex').slice(0, 12)
}

/** Derive a key from passphrase (for tests / migration helpers). */
export function deriveKeyFromPassphrase(passphrase, salt = 'uds-auth-skill') {
  return scryptSync(String(passphrase), String(salt), 32)
}
