import { installGatewayEvents } from './gateway-events.js'
import { isDesktopBootstrapEndpoint } from './desktop-bootstrap.js'
// Endpoints whose resource boundaries/projections are owned by dsh-acl wrappers.
const delegated = new Set([
  'session/list', 'session/search', 'session/create', 'session/selectModel', 'session/rename',
  'session/fork', 'session/prompt', 'session/attachment', 'session/updateQueue', 'session/cancel',
  'session/page', 'session/follow', 'session/projections', 'session/control', 'session/openWorkspacePath',
  'workspace/follow', 'workspace/insertSessionBefore', 'workspace/archiveSession', 'workspace/unarchiveSession',
  'workspace/pinSession', 'workspace/unpinSession', 'job/list', 'job/follow', 'job/kill',
  'terminal/list', 'terminal/create', 'terminal/follow', 'terminal/retain', 'terminal/write',
  'terminal/resize', 'terminal/close',
])
const catalogs = new Set(['session/modelCatalog', 'session/canOpenWorkspacePath', 'permissionPresets/catalog'])
// Anonymous mux must get dsh-acl's empty baseline, not a gateway error: a failed
// opening snapshot kills Desktop WorkspaceStateStream for good (sidebar never repaints
// after the authenticated reconnect).
const anonymousProjected = new Set(['workspace/follow'])
// That empty baseline makes Desktop try to create a default Workspace. Answer the
// anonymous attempt with "nothing created" (a legal result) instead of a denial,
// which surfaces as「无法创建默认工作区」; the real controller is never invoked.
const anonymousNoop = new Set(['workspace/initializeDefault'])

export function gatewayPolicy(descriptor) {
  const endpoint = `${descriptor.namespace}/${descriptor.method}`
  if (isDesktopBootstrapEndpoint(descriptor)) return 'desktop-bootstrap-projection'
  if (catalogs.has(endpoint)) return 'authenticated-catalog'
  if (delegated.has(endpoint)) return 'delegated-resource-acl'
  if (descriptor.invocation?.kind === 'context' && descriptor.invocation.context === 'agent') return 'session-bound'
  if ((descriptor.parameters || []).some(p => p.name === 'sessionId'
    || (p.source === 'lookup' && ['agent', 'workspaceFileScope'].includes(p.name)))) return 'session-bound'
  return 'admin-required'
}

/** Guard every unary/stream dispatch, including new or previously unwrapped Remote namespaces. */
export function installGatewayPolicy(gateway, { identity, assertPrincipal, assertSession, permissions, deny, desktopBootstrap }) {
  assertGatewayContract(gateway)
  const live = gateway.__udsGatewayPolicy || (gateway.__udsGatewayPolicy = {})
  Object.assign(live, { identity, assertPrincipal, assertSession, permissions, deny, desktopBootstrap })
  if (live.installed) return
  installGatewayEvents(gateway, live)
  live.installed = true
  const original = gateway.prepareInvocation.bind(gateway)
  const check = (request, descriptor) => {
    const principal = live.identity()
    if (principal === undefined) return
    const anonymous = !(principal?.empNo || principal?.userContext?.empNo)
    const endpoint = `${descriptor.namespace}/${descriptor.method}`
    if (anonymous && anonymousProjected.has(endpoint)) return
    if (anonymous && anonymousNoop.has(endpoint) && descriptor.mode === undefined) return 'noop'
    // Desktop opens its streams (account/watch, session lists, …) before the mux is
    // re-authenticated. A RemoteError is terminal for the client's $stream, so the
    // surface stays failed forever (e.g. account →「登录失败」). Park anonymous
    // streams with no data until the authenticated reconnect closes this carrier;
    // the client then reopens them under the real principal.
    if (anonymous && descriptor.mode !== undefined) return 'hold'
    if (isDesktopBootstrapEndpoint(descriptor) && typeof live.desktopBootstrap === 'function') {
      if (principal !== null) live.assertPrincipal(principal)
      if (!principal || !live.permissions(principal).canAccessSettings) return 'bootstrap'
    }
    live.assertPrincipal(principal)
    const policy = gatewayPolicy(descriptor)
    if (['admin-required', 'desktop-bootstrap-projection'].includes(policy)
      && !live.permissions(principal).canAccessSettings) live.deny('forbidden_settings')
    if (policy === 'session-bound') {
      const wires = []
      if (descriptor.invocation?.kind === 'context') wires.push(descriptor.invocation.wire)
      for (const p of descriptor.parameters || []) {
        if (p.name === 'sessionId' || (p.source === 'lookup' && ['agent', 'workspaceFileScope'].includes(p.name))) wires.push(p.wire)
      }
      for (const wire of wires) {
        const sid = request.args?.[wire]
        if (typeof sid !== 'string' || !sid) live.deny('session_forbidden')
        live.assertSession(sid)
      }
    }
  }
  gateway.prepareInvocation = async function(request, ...rest) {
    const descriptor = gateway.resolveDescriptor(request.namespace, request.method, `${request.namespace}/${request.method}`)
    check(request, descriptor)
    const prepared = await original(request, ...rest)
    const method = prepared.method
    prepared.method = function(...args) {
      const verdict = check(request, descriptor)
      if (verdict === 'noop') return undefined
      if (verdict === 'hold') return holdUntilAbort(prepared.invocation?.signal)
      if (verdict === 'bootstrap') return live.desktopBootstrap(request)
      const value = method.apply(this, args)
      if (descriptor.mode === undefined) return value
      return (async function* () {
        const stream = await value
        for await (const frame of stream) { check(request, descriptor); yield frame }
      })()
    }
    return prepared
  }
}

/** Empty stream that ends only when its carrier is aborted (no frames, no error). */
async function* holdUntilAbort(signal) {
  if (!signal || signal.aborted) return
  await new Promise((resolve) => signal.addEventListener('abort', () => resolve(), { once: true }))
}

export function assertGatewayContract(gateway) {
  for (const method of ['prepareInvocation', 'resolveDescriptor', 'openRemoteEvents', 'receiveRemoteEventResult']) {
    if (typeof gateway?.[method] !== 'function') throw new Error('unsupported_gateway_acl_contract')
  }
}
