/**
 * Auth session store — opaque sessionId + random bearer.
 * empNo is an attribute / secondary index, never the auth credential.
 */
export class SessionStore {
  /**
   * Create a verified session.
   * @param {object} userData
   * @param {number} ttlSeconds
   * @returns {Promise<{ sessionId: string, bearer: string, record: object }>}
   */
  async create(userData, ttlSeconds) {
    throw new Error('SessionStore#create must be implemented')
  }

  /** Lookup by bearer token (proof of possession). */
  async getByBearer(bearer) {
    throw new Error('SessionStore#getByBearer must be implemented')
  }

  /** Sync lookup for WS upgrade paths. */
  getByBearerSync(bearer) {
    throw new Error('SessionStore#getByBearerSync must be implemented')
  }

  async getBySessionId(sessionId) {
    throw new Error('SessionStore#getBySessionId must be implemented')
  }

  /** Return active UDS sessions and their upstream token for periodic validation. */
  async listUdsSessionsForValidation() {
    throw new Error('SessionStore#listUdsSessionsForValidation must be implemented')
  }

  async touch(sessionId, ttlSeconds) {
    throw new Error('SessionStore#touch must be implemented')
  }

  async revokeSession(sessionId) {
    throw new Error('SessionStore#revokeSession must be implemented')
  }

  async revokeBearer(bearer) {
    throw new Error('SessionStore#revokeBearer must be implemented')
  }

  /** Revoke all devices for an empNo. */
  async revokeEmpNo(empNo) {
    throw new Error('SessionStore#revokeEmpNo must be implemented')
  }

  /** Profile cache only — never proves authentication. */
  async setProfile(empNo, profile) {
    throw new Error('SessionStore#setProfile must be implemented')
  }

  async getProfile(empNo) {
    throw new Error('SessionStore#getProfile must be implemented')
  }

  async clear() {
    throw new Error('SessionStore#clear must be implemented')
  }

  // --- legacy compat shims (empNo-keyed) — prefer create/getByBearer ---

  /** @deprecated use getByBearer */
  async get(empNo) {
    throw new Error('SessionStore#get must be implemented')
  }

  /** @deprecated use create */
  async setex(empNo, seconds, userData) {
    throw new Error('SessionStore#setex must be implemented')
  }

  /** @deprecated use revokeEmpNo */
  async delete(empNo) {
    throw new Error('SessionStore#delete must be implemented')
  }

  async has(empNo) {
    throw new Error('SessionStore#has must be implemented')
  }

  async keys() {
    throw new Error('SessionStore#keys must be implemented')
  }
}

export const SESSION_COOKIE = 'UDS_SESSION'
export const SESSION_HEADER = 'x-uds-session'
/** Absolute session lifetime; idle expiry (cookieMaxAge) slides within it. */
export const SESSION_ABSOLUTE_MAX_SECONDS = 7 * 24 * 60 * 60
