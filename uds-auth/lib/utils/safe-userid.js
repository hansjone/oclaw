/**
 * SEC-14: normalize empNo / user directory segment — reject path semantics.
 */
import { resolve, join, sep } from 'node:path'

const MAX_LEN = 64
const SAFE_RE = /^[A-Za-z0-9._@+-]+$/
const WIN_RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i

/**
 * @param {unknown} empNo
 * @returns {string|null} sanitized id or null if rejected
 */
export function sanitizeUserId(empNo) {
  if (empNo == null) return null
  const s = String(empNo).trim()
  if (!s || s.length > MAX_LEN) return null
  if (s.includes('\0') || s.includes('..') || s.includes('/') || s.includes('\\') || s.includes(':')) {
    return null
  }
  if (!SAFE_RE.test(s)) return null
  if (WIN_RESERVED.test(s)) return null
  return s
}

/**
 * Resolve user workspace directory under root; returns null if escape would occur.
 * @param {string} workspaceRootAbs
 * @param {string} empNo
 * @returns {string|null}
 */
export function resolveUserDir(workspaceRootAbs, empNo) {
  const safe = sanitizeUserId(empNo)
  if (!safe) return null
  const root = resolve(String(workspaceRootAbs))
  const userPath = resolve(join(root, safe))
  if (userPath !== root && !userPath.startsWith(root + sep)) return null
  return userPath
}

/**
 * True when candidate is equal to or under base (after resolve).
 */
export function isPathInside(baseAbs, candidateAbs) {
  try {
    const base = resolve(String(baseAbs))
    const cand = resolve(String(candidateAbs))
    return cand === base || cand.startsWith(base + sep)
  } catch {
    return false
  }
}
