/** Host shellEnv adapter. Values are rebuilt after ordinary environment entries. */
export function createTaskEnvironment({ getOwner, rolesStore, capabilities, getWebServer, allowRawCredentials }) {
  const issued = new Map()
  const release = execution => {
    const key = execution?.token || execution
    const row = issued.get(key)
    if (!row) return
    capabilities.revoke(row.id)
    row.signal?.removeEventListener('abort', row.abort)
    clearTimeout(row.timer)
    row.off?.()
    issued.delete(key)
  }
  const contributor = {
    name: 'uds-auth',
    variables: {
      DSH_UDS_TASK_CAPABILITY: { description: 'Short-lived session-bound UDS capability; never print or persist.' },
      DSH_UDS_AUTH_BASE: { description: 'Owned loopback uds-auth endpoint of this Host.' },
    },
    resolve(execution) {
      release(execution)
      const empty = { DSH_UDS_TASK_CAPABILITY: '', DSH_UDS_AUTH_BASE: '' }
      const sid = execution?.agent?.session?.header?.id
      const owner = sid ? getOwner(String(sid)) : null
      const server = getWebServer()
      const port = Number(server?.port)
      if (!owner || rolesStore.isDisabled(owner) || !Number.isInteger(port) || port <= 0 || port > 65535
        || execution?.signal?.aborted) return empty
      const scopes = typeof allowRawCredentials === 'function' && allowRawCredentials()
        ? ['outbound', 'credentials']
        : ['outbound']
      const cap = capabilities.mint({
        empNo: owner, dshSessionId: String(sid), audience: 'uds-auth-agent',
        scopes, ttlSeconds: 600, mintedBy: 'host:shellEnv',
      })
      const row = { id: cap.id, sessionId: String(sid), signal: execution.signal, abort: () => release(execution) }
      issued.set(execution.token || execution, row)
      row.signal?.addEventListener('abort', row.abort, { once: true })
      row.timer = setTimeout(() => release(execution), cap.expiresAt - Date.now())
      row.timer.unref?.()
      return { DSH_UDS_TASK_CAPABILITY: cap.token, DSH_UDS_AUTH_BASE: `http://127.0.0.1:${port}/uds-auth` }
    },
  }
  return { contributor, release, finish(execution, result, jobs) {
    const row = issued.get(execution?.token || execution)
    const value = result?.value
    if (row && !result?.isError && ['background', 'promoted'].includes(value?.kind)
      && typeof value.jobId === 'string' && jobs?.events?.subscribe) {
      const job = jobs.list(row.sessionId).find(job => job.id === value.jobId)
      if (job && ['running', 'stopping'].includes(job.status)) {
        row.signal?.removeEventListener('abort', row.abort)
        row.signal = null
        row.off = jobs.events.subscribe({ owner: row.sessionId }, event => {
          if (event.job?.id === value.jobId && ['settled', 'stopping', 'removed'].includes(event.type)) release(execution)
        })
        return
      }
    }
    release(execution)
  }, dispose() {
    for (const key of [...issued.keys()]) release({ token: key })
  } }
}
