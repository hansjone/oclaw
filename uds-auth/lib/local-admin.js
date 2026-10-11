/**
 * Local admin via sealed box (decrypt-to-unlock).
 *
 * Ciphertext sources (first match wins):
 *   1) UDS_AUTH_LOCAL_ADMIN_BOX env
 *   2) $UDS_AUTH_DATA_DIR/local-admin.box or ~/.uds-auth/local-admin.box
 *
 * Operator keeps the passphrase offline. Unlock API tries AES-GCM open;
 * success → administrator session. Setting/replacing env alone does not
 * log anyone in — the key must decrypt the box.
 *
 * Generate a box:
 *   node scripts/seal-local-admin.mjs
 */
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
  scryptSync,
  timingSafeEqual,
  createHash,
} from 'node:crypto'
import { readFileSync, existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, resolve } from 'node:path'
import { ROLES, computePermissions, DEFAULT_FALLBACK_USERNAME } from './roles.js'
import { derivePasswordKey } from './utils/password-kdf.js'

export const LOCAL_ADMIN_BOX_ENV = 'UDS_AUTH_LOCAL_ADMIN_BOX'
/** @deprecated presence of KEY no longer grants access; use BOX + unlock */
export const LOCAL_ADMIN_ENV = 'UDS_AUTH_LOCAL_ADMIN_KEY'
export const LOCAL_ADMIN_BOX_FILENAME = 'local-admin.box'

export const LOCAL_ADMIN_COOKIE = 'UDS_LOCAL_ADMIN'
export const LOCAL_ADMIN_COOKIE_MAX_AGE = 7 * 24 * 60 * 60

/** Profile dir used when env box is missing (Desktop Host often lacks User env). */
export function resolveLocalAdminBoxFile(dataDir) {
  const root = String(dataDir || process.env.UDS_AUTH_DATA_DIR || '').trim()
    || join(homedir(), '.uds-auth')
  return resolve(root, LOCAL_ADMIN_BOX_FILENAME)
}

const MAGIC = 'uds-local-admin-v1'
const SCRYPT_N = 16384
const SCRYPT_R = 8
const SCRYPT_P = 1
const KEY_LEN = 32
const SALT_LEN = 16
const IV_LEN = 12

const MIN_PASSPHRASE_LEN = 12

function b64urlEncode(buf) {
  return Buffer.from(buf).toString('base64url')
}

function b64urlDecode(str) {
  return Buffer.from(String(str), 'base64url')
}

function deriveKey(passphrase, salt) {
  return scryptSync(passphrase, salt, KEY_LEN, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
    maxmem: 64 * 1024 * 1024,
  })
}

/**
 * Seal plaintext capability with passphrase → env-safe box string.
 * @param {string} passphrase
 * @returns {string}
 */
export function sealLocalAdminBox(passphrase) {
  const pw = String(passphrase || '')
  if (pw.length < MIN_PASSPHRASE_LEN) {
    throw new Error(`passphrase must be at least ${MIN_PASSPHRASE_LEN} characters`)
  }
  const salt = randomBytes(SALT_LEN)
  const iv = randomBytes(IV_LEN)
  const key = deriveKey(pw, salt)
  const cipher = createCipheriv('aes-256-gcm', key, iv)
  const plaintext = Buffer.from(`${MAGIC}|${DEFAULT_FALLBACK_USERNAME}`, 'utf8')
  const enc = Buffer.concat([cipher.update(plaintext), cipher.final()])
  const tag = cipher.getAuthTag()
  // version(1) | salt | iv | tag | ciphertext
  const out = Buffer.concat([Buffer.from([1]), salt, iv, tag, enc])
  return b64urlEncode(out)
}

/**
 * @param {string} box
 * @param {string} passphrase
 * @returns {{ ok: true, empNo: string } | { ok: false, reason: string }}
 */
export function openLocalAdminBox(box, passphrase) {
  const pw = String(passphrase || '')
  if (!box || !pw) return { ok: false, reason: 'missing' }
  let raw
  try {
    raw = b64urlDecode(box)
  } catch {
    return { ok: false, reason: 'bad_box' }
  }
  if (raw.length < 1 + SALT_LEN + IV_LEN + 16 + 1) {
    return { ok: false, reason: 'bad_box' }
  }
  const version = raw[0]
  if (version !== 1) return { ok: false, reason: 'bad_version' }
  let o = 1
  const salt = raw.subarray(o, o + SALT_LEN); o += SALT_LEN
  const iv = raw.subarray(o, o + IV_LEN); o += IV_LEN
  const tag = raw.subarray(o, o + 16); o += 16
  const enc = raw.subarray(o)
  try {
    const key = deriveKey(pw, salt)
    const decipher = createDecipheriv('aes-256-gcm', key, iv)
    decipher.setAuthTag(tag)
    const plain = Buffer.concat([decipher.update(enc), decipher.final()]).toString('utf8')
    const [magic, empNo] = plain.split('|')
    if (magic !== MAGIC || empNo !== DEFAULT_FALLBACK_USERNAME) {
      return { ok: false, reason: 'bad_payload' }
    }
    return { ok: true, empNo: DEFAULT_FALLBACK_USERNAME }
  } catch {
    return { ok: false, reason: 'decrypt_failed' }
  }
}

function readLocalAdminBoxFile() {
  try {
    const path = resolveLocalAdminBoxFile()
    if (!existsSync(path)) return null
    const raw = readFileSync(path, 'utf8')
    const line = String(raw || '').split(/\r?\n/).map((l) => l.trim()).find((l) => l && !l.startsWith('#'))
    if (!line) return null
    // Allow either bare box or KEY=value lines copied from seal CLI output.
    const m = line.match(/^(?:export\s+)?UDS_AUTH_LOCAL_ADMIN_BOX=(.+)$/)
    return String(m ? m[1] : line).trim().replace(/^["']|["']$/g, '') || null
  } catch {
    return null
  }
}

export function readLocalAdminBox() {
  const fromEnv = String(process.env[LOCAL_ADMIN_BOX_ENV] || '').trim()
  if (fromEnv) return fromEnv
  return readLocalAdminBoxFile()
}

/** Runtime unlock uses the same bounded, asynchronous KDF as password login. */
export async function openLocalAdminBoxAsync(box, passphrase) {
  if (!box || typeof passphrase !== 'string' || !passphrase) return { ok: false, reason: 'missing' }
  const raw = b64urlDecode(box)
  if (raw.length < 46 || raw.length > 256 || raw[0] !== 1) return { ok: false, reason: 'bad_box' }
  const key = await derivePasswordKey(passphrase, raw.subarray(1, 17))
  try {
    const decipher = createDecipheriv('aes-256-gcm', key, raw.subarray(17, 29))
    decipher.setAuthTag(raw.subarray(29, 45))
    const plain = Buffer.concat([decipher.update(raw.subarray(45)), decipher.final()]).toString('utf8')
    return plain === `${MAGIC}|${DEFAULT_FALLBACK_USERNAME}`
      ? { ok: true, empNo: DEFAULT_FALLBACK_USERNAME } : { ok: false, reason: 'bad_payload' }
  } catch {
    return { ok: false, reason: 'decrypt_failed' }
  }
}

export function isLocalAdminBoxConfigured() {
  const box = readLocalAdminBox()
  if (!box) return false
  try {
    const raw = b64urlDecode(box)
    return raw.length > 40 && raw[0] === 1
  } catch {
    return false
  }
}

/** Session cookie token after successful unlock (HMAC of box+empNo, not the passphrase). */
export function localAdminSessionToken(box = readLocalAdminBox()) {
  if (!box) return null
  return createHash('sha256').update(`sess:${box}`).digest('hex')
}

function safeEqualStr(a, b) {
  if (a == null || b == null) return false
  const ha = createHash('sha256').update(String(a)).digest()
  const hb = createHash('sha256').update(String(b)).digest()
  return timingSafeEqual(ha, hb)
}

function parseCookie(header, name) {
  if (!header || typeof header !== 'string') return null
  for (const part of header.split(';')) {
    const idx = part.indexOf('=')
    if (idx < 0) continue
    if (part.slice(0, idx).trim() !== name) continue
    try {
      return decodeURIComponent(part.slice(idx + 1).trim())
    } catch {
      return part.slice(idx + 1).trim()
    }
  }
  return null
}

/**
 * After unlock, browser holds UDS_LOCAL_ADMIN session token (not the passphrase).
 * This only proves a prior successful decrypt on this browser — does not skip decrypt on first login.
 */
export function requestHasLocalAdminSession(req) {
  const expect = localAdminSessionToken()
  if (!expect) return false
  const got = parseCookie(req?.headers?.cookie || '', LOCAL_ADMIN_COOKIE)
  return !!(got && safeEqualStr(got, expect))
}

export function buildLocalAdminUserContext() {
  const now = new Date().toISOString()
  return {
    empNo: DEFAULT_FALLBACK_USERNAME,
    userId: DEFAULT_FALLBACK_USERNAME,
    username: 'Local Admin',
    displayName: 'Local Admin',
    isAuthenticated: true,
    role: ROLES.FALLBACK_ADMIN,
    authMode: 'local-admin-unlock',
    authenticatedAt: now,
    lastActiveAt: now,
    sessionCreatedAt: now,
  }
}

export function buildLocalAdminIdentity(rolesStore) {
  const empNo = DEFAULT_FALLBACK_USERNAME
  const role = rolesStore?.getRole?.(empNo) || ROLES.FALLBACK_ADMIN
  const permissions = typeof rolesStore?.resolvePermissions === 'function'
    ? rolesStore.resolvePermissions(empNo, role)
    : computePermissions(role)
  return {
    empNo,
    role,
    permissions,
    userContext: buildLocalAdminUserContext(),
    kind: 'sealed_box',
  }
}

export function appendLocalAdminCookie(res, req) {
  const token = localAdminSessionToken()
  if (!token || !res || res.headersSent) return
  const secure = !!(req?.socket?.encrypted)
    || String(req?.headers?.['x-forwarded-proto'] || '').split(',')[0].trim().toLowerCase() === 'https'
  const parts = [
    `${LOCAL_ADMIN_COOKIE}=${token}`,
    `Max-Age=${LOCAL_ADMIN_COOKIE_MAX_AGE}`,
    'Path=/',
    'HttpOnly',
    'SameSite=Lax',
  ]
  if (secure) parts.push('Secure')
  const prev = res.getHeader('Set-Cookie')
  const next = parts.join('; ')
  if (!prev) res.setHeader('Set-Cookie', next)
  else if (Array.isArray(prev)) res.setHeader('Set-Cookie', [...prev, next])
  else res.setHeader('Set-Cookie', [String(prev), next])
}

export function logLocalAdminStatus(logger = console) {
  if (!isLocalAdminBoxConfigured()) {
    if (process.env[LOCAL_ADMIN_ENV]) {
      const log = logger?.warn?.bind(logger) || console.warn
      log(
        `[uds-auth] ${LOCAL_ADMIN_ENV} is ignored.`
        + ` Use ${LOCAL_ADMIN_BOX_ENV} (sealed ciphertext) + unlock with passphrase.`,
      )
    }
    return
  }
  const log = logger?.info?.bind(logger) || console.info
  log(
    `[uds-auth] local admin box configured (${LOCAL_ADMIN_BOX_ENV}).`
    + ' Unlock requires decrypting with your passphrase — env alone does not grant login.',
  )
}

/** Simple in-memory rate limit for unlock attempts. */
const unlockBuckets = new Map()

export function allowUnlockAttempt(ip) {
  const now = Date.now()
  let b = unlockBuckets.get(ip)
  if (!b || now > b.resetAt) {
    b = { count: 0, resetAt: now + 15 * 60 * 1000 }
    unlockBuckets.set(ip, b)
  }
  b.count += 1
  return b.count <= 10
}
