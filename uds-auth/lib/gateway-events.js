const catalogEvents = new Set(['commands/change', 'llm/adapters-updated', 'permission-presets/catalog-changed'])

/** The Gateway's $events carrier bypasses Remote method dispatch. Fence it too. */
export function installGatewayEvents(gateway, live) {
  if (typeof gateway.openRemoteEvents !== 'function' || typeof gateway.receiveRemoteEventResult !== 'function') {
    throw new Error('unsupported_gateway_event_contract')
  }
  const owners = new Map()
  const originalOpen = gateway.openRemoteEvents.bind(gateway)
  const originalResult = gateway.receiveRemoteEventResult.bind(gateway)
  const allowedSession = sid => {
    if (typeof sid !== 'string' || !sid) return false
    try { live.assertSession(sid); return true } catch { return false }
  }
  gateway.openRemoteEvents = async function* (...args) {
    const principal = live.identity()
    if (principal === undefined) { yield* originalOpen(...args); return }
    live.assertPrincipal(principal)
    let clientId
    const delivered = new Set()
    try {
      for await (const frame of originalOpen(...args)) {
        live.assertPrincipal(principal)
        if (frame.type === 'ready') {
          clientId = frame.clientId
          owners.set(clientId, { empNo: principal.empNo, sessionId: principal.sessionId })
          yield { ...frame, host: live.permissions(principal).canAccessSettings ? frame.host : { home: '' } }
        } else if (frame.type === 'waterfall') {
          if (allowedSession(frame.agentId)) { delivered.add(frame.eventId); yield frame }
        } else if (frame.type === 'cancel') {
          if (delivered.delete(frame.eventId)) yield frame
        } else if (frame.type === 'emit') {
          const first = frame.args?.[0]
          let sid
          if (frame.event === 'api-session/added') sid = first?.id ?? first?.sessionId
          else if (['api-session/activity', 'api-session/error', 'api-session/removed', 'api-session/status', 'agent-preset/selected'].includes(frame.event)) sid = first
          else if (frame.event === 'goal/activation-changed') sid = first?.sessionId
          if (sid !== undefined ? allowedSession(sid)
            : catalogEvents.has(frame.event) || live.permissions(principal).canAccessSettings) yield frame
        }
      }
    } finally { if (clientId) owners.delete(clientId) }
  }
  gateway.receiveRemoteEventResult = function(client, result, ...rest) {
    const principal = live.identity()
    if (principal !== undefined) {
      live.assertPrincipal(principal)
      const owner = owners.get(result.clientId)
      if (!owner || owner.empNo !== principal.empNo || owner.sessionId !== principal.sessionId) live.deny('event_client_forbidden')
      const pending = gateway.pendingRemoteEvents?.get(result.eventId)
      if (pending && !allowedSession(pending.frame?.agentId)) live.deny('session_forbidden')
    }
    return originalResult(client, result, ...rest)
  }
}
