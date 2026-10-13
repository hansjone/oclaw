/**
 * Periodic UAC token check for QR-authenticated sessions.
 *
 * The UAC token is what actually expires: it must still read the user's department
 * profile from icenterapi for UAC-backed work (skills, cron) to succeed. A rejected
 * token never signs anyone out — conversations and night-time cron keep their local
 * session. The session is only flagged; the client then shows a QR prompt and a scan
 * refreshes the token in place (see handleQrProxy → refreshSessionToken).
 *
 * Network errors, 5xx and malformed responses say nothing about the token and leave
 * the previous verdict unchanged.
 */

/** 2 hours between rounds. */
export const UDS_TOKEN_CHECK_INTERVAL_MS = 2 * 60 * 60 * 1000
/** First round shortly after start so flags lost on restart come back quickly. */
export const UDS_TOKEN_FIRST_CHECK_MS = 60 * 1000

/** searchUserByEmpNoToken / verifyEmpNoAndToken failure reasons that reject the token. */
export const DEFINITIVE_PROFILE_FAILURES = new Set([
  'http_auth',        // 401 / 403
  'biz_code',         // icenterapi business error
  'empty',            // token cannot see this employee
  'emp_mismatch',
  'ambiguous',
  'reserved_subject',
  'missing_args',     // session carries no token
])

export class UdsTokenMonitor {
  /**
   * @param {{
   *   sessionStore: { listUdsSessionsForValidation(): Promise<any[]> },
   *   verify: (empNo: string, token: string, opts: { onFailure?: (out: any) => void }) => Promise<object|null>,
   *   logger?: { info?: Function, warn?: Function },
   * }} deps
   */
  constructor(deps) {
    this.deps = deps
    /** sessionId → { empNo, reason, since } for sessions whose UAC token was rejected. */
    this.rejected = new Map()
  }

  async _classify(empNo, token) {
    if (!token) return { verdict: 'invalid', reason: 'missing_args' }
    let failure = null
    try {
      const profile = await this.deps.verify(empNo, token, { onFailure: (out) => { failure = out } })
      if (profile) return { verdict: 'ok' }
    } catch (err) {
      return { verdict: 'unknown', reason: err?.message || 'error' }
    }
    const reason = String(failure?.reason || 'unknown')
    return { verdict: DEFINITIVE_PROFILE_FAILURES.has(reason) ? 'invalid' : 'unknown', reason }
  }

  /** True when this session's UAC token was rejected and has not been refreshed since. */
  isTokenRejected(sessionId) {
    return this.rejected.has(String(sessionId || ''))
  }

  /** A fresh, verified token was written into these sessions. */
  markRefreshed(sessionIds) {
    for (const id of sessionIds) this.rejected.delete(String(id))
  }

  /** Verify every live QR session's token (one icenterapi call per empNo+token). */
  async runRound() {
    const { sessionStore, logger } = this.deps
    const sessions = await sessionStore.listUdsSessionsForValidation()
    const verdicts = new Map()
    const stats = { checked: 0, ok: 0, rejected: 0, inconclusive: 0 }
    for (const session of sessions) {
      stats.checked++
      const key = `${session.empNo}\0${session.token || ''}`
      let result = verdicts.get(key)
      if (!result) {
        result = await this._classify(session.empNo, session.token)
        verdicts.set(key, result)
        if (result.verdict === 'unknown') {
          logger?.warn?.('[uds-auth] UAC token check inconclusive for %s (%s); keeping previous status', session.empNo, result.reason)
        } else if (result.verdict === 'invalid') {
          logger?.info?.('[uds-auth] UAC token rejected for %s (%s); prompting a QR refresh', session.empNo, result.reason)
        }
      }
      if (result.verdict === 'ok') {
        this.rejected.delete(session.sessionId)
        stats.ok++
      } else if (result.verdict === 'invalid') {
        if (!this.rejected.has(session.sessionId)) {
          this.rejected.set(session.sessionId, { empNo: session.empNo, reason: result.reason, since: Date.now() })
        }
        stats.rejected++
      } else {
        stats.inconclusive++
      }
    }
    const live = new Set(sessions.map((s) => s.sessionId))
    for (const id of this.rejected.keys()) if (!live.has(id)) this.rejected.delete(id)
    return stats
  }
}
