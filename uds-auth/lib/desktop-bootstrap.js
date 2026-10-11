// Compatibility with the unmodified DSH Desktop welcome RPC sequence. These
// projections contain no account attempt, real credential reference, or config.
export const DESKTOP_BOOTSTRAP_REF = 'UDS_AUTH_DESKTOP_PROVIDER_CONFIGURED'
const namespace = 'uds-auth-desktop-bootstrap'
const endpoints = new Set(['settings/describe', 'llm/listConfigurableProviders', 'credentials/describe', 'account/getState'])

export function isDesktopBootstrapEndpoint(descriptor) {
  return !descriptor.mode && endpoints.has(`${descriptor.namespace}/${descriptor.method}`)
}

function view(ns, value) {
  return { ns, value, autoGenerate: false, schema: { type: 'object', dict: {} },
    applies: 'live', secrets: [], revision: 0 }
}

/** Read only Host-owned metadata; request arguments can never select a secret. */
export function createDesktopBootstrap({ getService, deny }) {
  const settings = () => getService('settings')?.describe?.({ redactSecrets: true }) || []
  // Every read is best-effort: one failing provider or reference must not fail the
  // whole welcome read (Desktop treats a failed read as "no API key").
  const configured = async () => {
    let rows = []
    try { rows = settings() } catch { rows = [] }
    const refs = new Set()
    const official = rows.find(row => row.ns === 'llm-deepseek')?.value?.apiKeyEnv
    if (typeof official === 'string') refs.add(official)
    let providers = []
    try { providers = getService('llm')?.listConfigurableProviders?.() || [] } catch { providers = [] }
    for (const provider of providers) {
      let value = rows.find(row => row.ns === provider?.settingsNs)?.value
      for (const key of provider?.settingsPath || []) value = value && Object.hasOwn(value, key) ? value[key] : undefined
      if (typeof value?.apiKeyEnv === 'string') refs.add(value.apiKeyEnv)
    }
    const credentials = getService('credentials')
    for (const ref of refs) {
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(ref)) continue
      try {
        if ((await credentials?.describe?.(ref))?.configured === true) return true
      } catch { /* try the next reference */ }
    }
    return false
  }
  return async request => {
    const endpoint = `${request.namespace}/${request.method}`
    switch (endpoint) {
      case 'settings/describe': {
        const preference = settings().find(row => row.ns === 'locale')?.value?.preference
        return { writable: false, hasDocument: false, namespaces: [
          view('locale', { ...(typeof preference === 'string' && /^[A-Za-z-]{2,16}$/.test(preference) ? { preference } : {}) }),
          view(namespace, { apiKeyEnv: DESKTOP_BOOTSTRAP_REF }),
        ] }
      }
      case 'llm/listConfigurableProviders':
        return [{ provider: namespace, displayName: 'Host provider', settingsNs: namespace, settingsPath: [] }]
      case 'credentials/describe': {
        const refs = request.args?.refs
        if (!Array.isArray(refs) || refs.length > 1 || refs.some(ref => ref !== DESKTOP_BOOTSTRAP_REF)) deny('forbidden_settings')
        return refs.length ? { [DESKTOP_BOOTSTRAP_REF]: { configured: await configured(), writable: false } } : {}
      }
      case 'account/getState': {
        let state
        try { state = await getService('deepseekAccount')?.getState?.() } catch { state = undefined }
        return { status: state?.status === 'credential-stored' ? 'credential-stored' : 'signed-out', attempt: null,
          links: { usageUrl: 'https://platform.deepseek.com/usage', topUpUrl: 'https://platform.deepseek.com/top_up' } }
      }
      default: return deny('login_required')
    }
  }
}
