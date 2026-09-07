/**
 * uds-auth browser half — conversation.session.header.utilities (left of log-download) + settings.section.
 * Auth: empNo cookie + token verified server-side via user-info.
 * Fallback: username/password when UAC/QR unavailable.
 */
window.__ModuleLoader__.load({
  id: 'uds-auth',
  factory: (require) => {
    const module = { exports: {} }
    const exports = module.exports
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' })

    const React = require('react')
    const h = React.createElement
    const { useCallback, useEffect, useLayoutEffect, useRef, useState } = React

    const name = 'uds-auth'
    const inject = ['slots']
    const PAGE_SIZE = 50

    const CSS = [
      '.uds-auth-host{position:relative;display:inline-flex;align-items:center;height:32px;margin:0;flex-shrink:0;pointer-events:auto}',
      '.uds-auth-badge{display:inline-flex;align-items:center;justify-content:center;gap:4px;max-width:min(180px,30vw);min-width:auto;height:32px;padding:6px 12px;border-radius:18px;background:transparent;border:1px solid var(--dsw-alias-border-l2);color:var(--dsw-alias-label-primary);font-size:13px;font-weight:400;line-height:20px;cursor:pointer;font-family:var(--dsw-font-family)}',
      '.uds-auth-badge:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.uds-auth-badge-unauth{color:var(--dsw-alias-label-tertiary,#8f959e)}',
      '.uds-auth-avatar{width:18px;height:18px;border-radius:50%;background:linear-gradient(135deg,var(--dsw-alias-state-business-primary,#3370ff),var(--dsw-alias-state-success-primary,#20a162));display:inline-flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#fff;flex-shrink:0}',
      '.uds-auth-badge-unauth .uds-auth-avatar{background:var(--dsw-alias-bg-module-platform,rgba(242,243,245,1));color:var(--dsw-alias-label-tertiary,#8f959e)}',
      '.uds-auth-badge-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.uds-auth-role{font-size:10px;padding:1px 6px;border-radius:10px;font-weight:600;flex-shrink:0}',
      '.uds-auth-role-super_admin{background:rgba(213,73,65,.12);color:var(--dsw-alias-state-error-primary,#d54941)}',
      '.uds-auth-role-admin{background:rgba(217,119,6,.12);color:var(--dsw-alias-state-warn-primary,#d97706)}',
      '.uds-auth-role-fallback_admin{background:rgba(51,112,255,.12);color:var(--dsw-alias-state-business-primary,#3370ff)}',
      '.uds-auth-panel{position:fixed;z-index:1200;width:min(300px,calc(100vw - 24px));max-height:min(70vh,560px);overflow:auto;background:var(--dsw-alias-bg-layer-1,#fff);border-radius:8px;border:1px solid var(--dsw-alias-border-l2,#dee0e3);box-shadow:0 8px 28px rgba(0,0,0,.12)}',
      '.uds-auth-info{padding:14px 16px;border-bottom:1px solid var(--dsw-alias-border-l1,#eef0f3)}',
      '.uds-auth-info-name{font-weight:600;margin-bottom:4px;color:var(--dsw-alias-label-primary,#1f2329);font-size:14px}',
      '.uds-auth-info-detail{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);margin-top:2px;display:flex;justify-content:space-between;gap:8px}',
      '.uds-auth-info-detail-label{color:var(--dsw-alias-label-tertiary,#8f959e)}',
      '.uds-auth-qr{padding:16px;text-align:center}',
      '.uds-auth-qr img{display:block;margin:0 auto;width:160px;height:160px}',
      '.uds-auth-qr-status{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);margin-top:8px}',
      '.uds-auth-btn{display:block;width:calc(100% - 32px);margin:8px 16px 0;padding:8px 12px;border-radius:4px;cursor:pointer;font-size:13px;text-align:left;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);background:var(--dsw-alias-bg-module-platform,#f4f5f7);color:var(--dsw-alias-label-primary,#1f2329)}',
      '.uds-auth-btn:hover{background:var(--dsw-alias-interactive-bg-hover,#f7f8fa)}',
      '.uds-auth-btn-primary{background:var(--dsw-alias-state-business-primary,#3370ff);color:#fff;border-color:transparent;text-align:center}',
      '.uds-auth-btn-primary:hover{opacity:.9}',
      '.uds-auth-btn-danger{margin-bottom:16px;background:rgba(213,73,65,.08);color:var(--dsw-alias-state-error-primary,#d54941);border-color:rgba(213,73,65,.2)}',
      '.uds-auth-btn-link{background:transparent;border:none;color:var(--dsw-alias-state-business-primary,#3370ff);text-align:center;padding:4px 12px;margin:4px 16px 12px;width:calc(100% - 32px);font-size:12px;cursor:pointer}',
      '.uds-auth-fallback{padding:12px 16px 16px}',
      '.uds-auth-fallback label{display:block;font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);margin:8px 0 4px}',
      '.uds-auth-fallback input{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:6px;font-size:13px}',
      '.uds-auth-fallback-hint{font-size:11px;color:var(--dsw-alias-label-tertiary,#8f959e);margin:8px 0 0;line-height:1.4}',
      '.uds-auth-table{width:100%;border-collapse:collapse;font-size:12px}',
      '.uds-auth-table th,.uds-auth-table td{padding:6px 8px;text-align:left;border-bottom:1px solid var(--dsw-alias-border-l1,#eef0f3)}',
      '.uds-auth-add{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}',
      '.uds-auth-add input,.uds-auth-add select{padding:6px 8px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:4px;font-size:12px}',
      '.uds-auth-add input{flex:1;min-width:120px}',
      '.uds-auth-del{padding:3px 8px;background:rgba(213,73,65,.1);color:var(--dsw-alias-state-error-primary,#d54941);border:1px solid rgba(213,73,65,.2);border-radius:3px;cursor:pointer;font-size:11px}',
      '.uds-auth-pager{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:12px;font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);flex-wrap:wrap}',
      '.uds-auth-pager button{padding:4px 10px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:4px;background:var(--dsw-alias-bg-module-platform,#f4f5f7);cursor:pointer;font-size:12px}',
      '.uds-auth-pager button:disabled{opacity:.4;cursor:not-allowed}',
      '.uds-auth-search{display:flex;gap:8px;margin-bottom:12px}',
      '.uds-auth-search input{flex:1;padding:8px 10px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:6px;font-size:13px}',
      '.uds-auth-settings{box-sizing:border-box;display:flex;flex-direction:column;gap:20px;min-height:0;padding:4px 4px 24px;color:var(--dsw-alias-label-primary,#1f2329)}',
      '.uds-auth-settings h2{margin:0;font-size:20px;font-weight:600;line-height:28px}',
      '.uds-auth-settings-intro{margin:4px 0 0;font-size:13px;color:var(--dsw-alias-label-secondary,#646a73)}',
      '.uds-auth-settings-card{border:1px solid var(--dsw-alias-border-l2,#dee0e3);border-radius:12px;padding:16px;background:var(--dsw-alias-bg-layer-1,transparent)}',
      '.uds-auth-settings-card h3{margin:0 0 12px;font-size:15px;font-weight:600}',
      '.uds-auth-settings-field{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}',
      '.uds-auth-settings-field label{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73)}',
      '.uds-auth-settings-field input{padding:8px 10px;border:1px solid var(--dsw-alias-border-l2,#dfe1e5);border-radius:6px;font-size:13px;background:var(--dsw-alias-bg-module-platform,#f4f5f7);color:inherit}',
      '.uds-auth-settings-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
      '.uds-auth-settings-msg{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73)}',
      '.uds-auth-settings-msg.ok{color:var(--dsw-alias-state-success-primary,#20a162)}',
      '.uds-auth-settings-msg.err{color:var(--dsw-alias-state-error-primary,#d54941)}',
      '.uds-auth-settings-empty{padding:24px;text-align:center;color:var(--dsw-alias-label-tertiary,#8f959e);font-size:13px}',
    ].join('')

    function getCookie(cookieName) {
      const prefix = cookieName + '='
      const parts = String(document.cookie || '').split(';')
      for (const part of parts) {
        const v = part.trim()
        if (v.startsWith(prefix)) return decodeURIComponent(v.slice(prefix.length))
      }
      return null
    }

    function setCookie(cookieName, value, days) {
      const d = new Date()
      d.setTime(d.getTime() + days * 86400000)
      document.cookie = encodeURIComponent(cookieName) + '=' + encodeURIComponent(value) + ';expires=' + d.toUTCString() + ';path=/'
    }

    function clearAuthCookies() {
      for (const key of ['PORTALSSOUser', 'PORTALSSOCookie', 'ZTEDPGSSOUser', 'ZTEDPGSSOCookie', 'UDS_FALLBACK_USER']) {
        setCookie(key, '', -1)
      }
    }

    function getEmpNo() {
      return getCookie('PORTALSSOUser') || getCookie('ZTEDPGSSOUser') || getCookie('UDS_FALLBACK_USER') || null
    }

    function getAuthToken() {
      return getCookie('PORTALSSOCookie') || getCookie('ZTEDPGSSOCookie') || null
    }

    function roleLabel(role) {
      return ({ super_admin: '\u8d85\u7ba1', admin: '\u7ba1\u7406\u5458', fallback_admin: '\u5e94\u6025', user: '' })[role] || ''
    }

    async function fetchJson(url, options) {
      const res = await fetch(url, options)
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const err = new Error(data.error || res.statusText || 'request failed')
        err.status = res.status
        err.data = data
        throw err
      }
      return data
    }

    function useOutsideClose(ref, open, setOpen) {
      useEffect(() => {
        if (!open) return undefined
        const onPointer = (event) => {
          if (ref.current && !ref.current.contains(event.target)) setOpen(false)
        }
        document.addEventListener('pointerdown', onPointer, true)
        return () => document.removeEventListener('pointerdown', onPointer, true)
      }, [open, ref, setOpen])
    }

    function UserManagementPanel() {
      const [users, setUsers] = useState([])
      const [total, setTotal] = useState(0)
      const [page, setPage] = useState(1)
      const [totalPages, setTotalPages] = useState(1)
      const [q, setQ] = useState('')
      const [qDraft, setQDraft] = useState('')
      const [newEmpNo, setNewEmpNo] = useState('')
      const [newRole, setNewRole] = useState('user')
      const [error, setError] = useState('')
      const [loading, setLoading] = useState(true)

      const reload = useCallback(async () => {
        setLoading(true)
        setError('')
        try {
          const qs = new URLSearchParams({
            page: String(page),
            pageSize: String(PAGE_SIZE),
          })
          if (q) qs.set('q', q)
          const data = await fetchJson('/uds-auth/api/users?' + qs.toString())
          setUsers(data.users || [])
          setTotal(data.total || 0)
          setTotalPages(data.totalPages || 1)
        } catch (err) {
          setError(err.data?.error || err.message || '\u52a0\u8f7d\u5931\u8d25')
          setUsers([])
        } finally {
          setLoading(false)
        }
      }, [page, q])

      useEffect(() => { reload() }, [reload])

      return h('div', { className: 'uds-auth-settings-card' },
        h('h3', null, '\u7528\u6237\u7ba1\u7406'),
        h('div', { className: 'uds-auth-search' },
          h('input', {
            value: qDraft,
            placeholder: '\u641c\u7d22\u5de5\u53f7',
            onChange: (e) => setQDraft(e.target.value),
            onKeyDown: (e) => {
              if (e.key === 'Enter') { setPage(1); setQ(qDraft.trim()) }
            },
          }),
          h('button', {
            type: 'button',
            className: 'uds-auth-btn uds-auth-btn-primary',
            style: { width: 'auto', margin: 0 },
            onClick: () => { setPage(1); setQ(qDraft.trim()) },
          }, '\u641c\u7d22'),
        ),
        error && h('div', { className: 'uds-auth-settings-msg err', role: 'alert' }, error),
        loading
          ? h('div', { className: 'uds-auth-settings-empty' }, '\u52a0\u8f7d\u4e2d...')
          : h('table', { className: 'uds-auth-table' },
            h('thead', null, h('tr', null, h('th', null, '\u5de5\u53f7'), h('th', null, '\u89d2\u8272'), h('th', null, '\u64cd\u4f5c'))),
            h('tbody', null, users.length === 0
              ? h('tr', null, h('td', { colSpan: 3 }, '\u6682\u65e0\u7528\u6237'))
              : users.map((u) => h('tr', { key: u.empNo },
                h('td', null, u.empNo),
                h('td', null,
                  h('select', {
                    value: u.role,
                    onChange: async (e) => {
                      try {
                        await fetchJson('/uds-auth/api/users/role', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ empNo: u.empNo, role: e.target.value }),
                        })
                        reload()
                      } catch (err) { window.alert(err.data?.error || err.message) }
                    },
                  },
                  h('option', { value: 'user' }, '\u666e\u901a\u7528\u6237'),
                  h('option', { value: 'admin' }, '\u7ba1\u7406\u5458'),
                  h('option', { value: 'super_admin' }, '\u8d85\u7ea7\u7ba1\u7406\u5458'),
                  ),
                ),
                h('td', null,
                  h('button', {
                    type: 'button', className: 'uds-auth-del',
                    onClick: async () => {
                      if (!window.confirm('\u786e\u8ba4\u5220\u9664 ' + u.empNo + '?')) return
                      try {
                        await fetchJson('/uds-auth/api/users/delete', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ empNo: u.empNo }),
                        })
                        reload()
                      } catch (err) { window.alert(err.data?.error || err.message) }
                    },
                  }, '\u5220\u9664'),
                ),
              )),
            ),
          ),
        h('div', { className: 'uds-auth-pager' },
          h('span', null, '\u5171 ' + total + ' \u4eba\uff0c\u7b2c ' + page + ' / ' + totalPages + ' \u9875'),
          h('span', null,
            h('button', {
              type: 'button', disabled: page <= 1 || loading,
              onClick: () => setPage((p) => Math.max(1, p - 1)),
            }, '\u4e0a\u4e00\u9875'),
            ' ',
            h('button', {
              type: 'button', disabled: page >= totalPages || loading,
              onClick: () => setPage((p) => p + 1),
            }, '\u4e0b\u4e00\u9875'),
          ),
        ),
        h('div', { className: 'uds-auth-add' },
          h('input', { value: newEmpNo, placeholder: '\u5de5\u53f7', onChange: (e) => setNewEmpNo(e.target.value) }),
          h('select', { value: newRole, onChange: (e) => setNewRole(e.target.value) },
            h('option', { value: 'user' }, '\u666e\u901a\u7528\u6237'),
            h('option', { value: 'admin' }, '\u7ba1\u7406\u5458'),
            h('option', { value: 'super_admin' }, '\u8d85\u7ea7\u7ba1\u7406\u5458'),
          ),
          h('button', {
            type: 'button', className: 'uds-auth-btn uds-auth-btn-primary', style: { width: 'auto', margin: 0 },
            onClick: async () => {
              const empNo = newEmpNo.trim()
              if (!empNo) return
              try {
                await fetchJson('/uds-auth/api/users', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ empNo, role: newRole }),
                })
                setNewEmpNo('')
                reload()
              } catch (err) { window.alert(err.data?.error || err.message) }
            },
          }, '\u6dfb\u52a0'),
        ),
      )
    }

    function AuthSettingsSection() {
      const [me, setMe] = useState(null)
      const [form, setForm] = useState({
        uacBaseUrl: '',
        userSearchUrl: '',
        loginSystemCode: '',
        originSystemCode: '',
      })
      const [fallbackEnabled, setFallbackEnabled] = useState(false)
      const [fallbackPwd, setFallbackPwd] = useState('')
      const [msg, setMsg] = useState('')
      const [msgKind, setMsgKind] = useState('')
      const [busy, setBusy] = useState(false)

      useEffect(() => {
        let cancelled = false
        ;(async () => {
          try {
            const data = await fetchJson('/uds-auth/api/me')
            if (!cancelled) setMe(data?.data || null)
          } catch {
            if (!cancelled) setMe(null)
          }
          try {
            const cfg = await fetchJson('/uds-auth/config.get')
            if (!cancelled && cfg?.value) setForm((prev) => ({ ...prev, ...cfg.value }))
          } catch { /* ignore */ }
          try {
            const st = await fetchJson('/uds-auth/api/fallback/status')
            if (!cancelled) setFallbackEnabled(!!st.enabled)
          } catch { /* ignore */ }
        })()
        return () => { cancelled = true }
      }, [])

      const perms = me?.permissions || {}
      const canManage = !!perms.canManageUsers
      const canSettings = !!perms.canAccessSettings

      const saveConfig = async () => {
        setBusy(true)
        setMsg('')
        try {
          await fetchJson('/uds-auth/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(form),
          })
          setMsgKind('ok')
          setMsg('\u914d\u7f6e\u5df2\u4fdd\u5b58')
        } catch (err) {
          setMsgKind('err')
          setMsg(err.data?.error || err.message || '\u4fdd\u5b58\u5931\u8d25')
        } finally {
          setBusy(false)
        }
      }

      const field = (key, label) => h('div', { className: 'uds-auth-settings-field' },
        h('label', { htmlFor: 'uds-auth-' + key }, label),
        h('input', {
          id: 'uds-auth-' + key,
          value: form[key] || '',
          disabled: !canSettings || busy,
          onChange: (e) => setForm((prev) => ({ ...prev, [key]: e.target.value })),
        }),
      )

      return h('section', { className: 'uds-auth-settings', 'aria-label': 'UDS Auth' },
        h('header', null,
          h('h2', null, 'UDS \u8ba4\u8bc1'),
          h('p', { className: 'uds-auth-settings-intro' },
            '\u5de5\u53f7+token \u53cc\u6821\u9a8c\uff1bUAC \u6302\u6b7b\u65f6\u7528\u5e94\u6025\u8d26\u53f7 administrator \u5bc6\u7801\u767b\u5f55\u3002'),
        ),
        !me && h('div', { className: 'uds-auth-settings-empty' }, '\u8bf7\u5148\u767b\u5f55\u540e\u67e5\u770b\u6b64\u9875'),
        me && !canSettings && !canManage && h('div', { className: 'uds-auth-settings-empty' }, '\u5f53\u524d\u8d26\u53f7\u65e0\u8bbe\u7f6e\u6743\u9650'),
        canSettings && h('div', { className: 'uds-auth-settings-card' },
          h('h3', null, '\u90e8\u7f72\u914d\u7f6e'),
          field('uacBaseUrl', 'UAC Base URL'),
          field('userSearchUrl', '\u7528\u6237\u641c\u7d22 URL\uff08token \u6821\u9a8c\uff09'),
          field('loginSystemCode', 'loginSystemCode'),
          field('originSystemCode', 'originSystemCode'),
          h('div', { className: 'uds-auth-settings-actions' },
            h('button', {
              type: 'button',
              className: 'uds-auth-btn uds-auth-btn-primary',
              style: { width: 'auto', margin: 0 },
              disabled: busy,
              onClick: saveConfig,
            }, busy ? '\u4fdd\u5b58\u4e2d...' : '\u4fdd\u5b58\u914d\u7f6e'),
            msg && h('span', { className: 'uds-auth-settings-msg ' + msgKind }, msg),
          ),
        ),
        canManage && h('div', { className: 'uds-auth-settings-card' },
          h('h3', null, '\u5e94\u6025\u767b\u5f55\uff08UAC \u4e0d\u53ef\u7528\uff09'),
          h('p', { className: 'uds-auth-settings-intro' },
            '\u72b6\u6001\uff1a' + (fallbackEnabled ? '\u5df2\u542f\u7528' : '\u672a\u8bbe\u7f6e\u5bc6\u7801\uff08\u672a\u542f\u7528\uff09')
            + '\u3002\u7528\u6237\u540d\u56fa\u5b9a\u4e3a administrator\uff0c\u4ec5\u5728\u626b\u7801\u4e0d\u53ef\u7528\u65f6\u4ece\u767b\u5f55\u9762\u677f\u5207\u6362\u3002'),
          h('div', { className: 'uds-auth-settings-field' },
            h('label', { htmlFor: 'uds-auth-fallback-pwd' }, '\u5e94\u6025\u5bc6\u7801\uff08\u81f3\u5c11 6 \u4f4d\uff09'),
            h('input', {
              id: 'uds-auth-fallback-pwd',
              type: 'password',
              value: fallbackPwd,
              onChange: (e) => setFallbackPwd(e.target.value),
              autoComplete: 'new-password',
            }),
          ),
          h('div', { className: 'uds-auth-settings-actions' },
            h('button', {
              type: 'button',
              className: 'uds-auth-btn uds-auth-btn-primary',
              style: { width: 'auto', margin: 0 },
              onClick: async () => {
                try {
                  await fetchJson('/uds-auth/api/fallback/password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: fallbackPwd }),
                  })
                  setFallbackPwd('')
                  setFallbackEnabled(true)
                  window.alert('\u5e94\u6025\u5bc6\u7801\u5df2\u8bbe\u7f6e')
                } catch (err) { window.alert(err.data?.error || err.message) }
              },
            }, '\u4fdd\u5b58\u5e94\u6025\u5bc6\u7801'),
            fallbackEnabled && h('button', {
              type: 'button',
              className: 'uds-auth-btn uds-auth-btn-danger',
              style: { width: 'auto', margin: 0 },
              onClick: async () => {
                if (!window.confirm('\u786e\u8ba4\u6e05\u9664\u5e94\u6025\u5bc6\u7801\uff1f')) return
                try {
                  await fetchJson('/uds-auth/api/fallback/clear', { method: 'POST' })
                  setFallbackEnabled(false)
                } catch (err) { window.alert(err.data?.error || err.message) }
              },
            }, '\u6e05\u9664'),
          ),
        ),
        canManage && h(UserManagementPanel, null),
      )
    }

    function AuthBadge() {
      const rootRef = useRef(null)
      const [open, setOpen] = useState(false)
      const [anchor, setAnchor] = useState(null)
      const [user, setUser] = useState(null)
      

      const [loading, setLoading] = useState(true)
      const [config, setConfig] = useState({ loginSystemCode: '100000455558', originSystemCode: '' })
      const [qrStatus, setQrStatus] = useState('')
      const [qrImg, setQrImg] = useState('')
      const [loginMode, setLoginMode] = useState('qr')
      const [fallbackEnabled, setFallbackEnabled] = useState(false)
      const [fbUser, setFbUser] = useState('administrator')
      const [fbPass, setFbPass] = useState('')
      const [fbBusy, setFbBusy] = useState(false)
      const [fbErr, setFbErr] = useState('')
      const qrRef = useRef({ key: null, value: null, timer: null })

      const stopQr = useCallback(() => {
        if (qrRef.current.timer) { clearInterval(qrRef.current.timer); qrRef.current.timer = null }
        qrRef.current.key = null
        qrRef.current.value = null
      }, [])

      const refreshUser = useCallback(async () => {
        try {
          const me = await fetchJson('/uds-auth/api/me')
          if (!me?.authenticated || !me?.data) {
            setUser(null)
            return
          }
          const d = me.data
          setUser({
            empNo: d.empNo || d.userId,
            userName: d.displayName || d.username || d.userName || d.empNo,
            department: d.department || '',
            email: d.email || '',
            phone: d.phone || '',
            role: d.role || 'user',
            permissions: d.permissions || {},
          })
        } catch {
          setUser(null)
        } finally {
          setLoading(false)
        }
      }, [])

      const startQr = useCallback(async () => {
        stopQr()
        setQrStatus('\u6b63\u5728\u751f\u6210\u4e8c\u7ef4\u7801...')
        setQrImg('')
        try {
          const started = await fetchJson('/uds-auth/qr-start')
          const { qrCodeStr, qrCodeKey, qrCodeValue, loginSystemCode, originSystemCode } = started
          qrRef.current.key = qrCodeKey
          qrRef.current.value = qrCodeValue
          setQrImg('/uds-auth/qr?data=' + encodeURIComponent(qrCodeStr))
          setQrStatus('\u8bf7\u4f7f\u7528 iCenter \u626b\u7801\u767b\u5f55...')
          qrRef.current.timer = setInterval(async () => {
            if (!qrRef.current.key) return
            try {
              const verify = await fetchJson(
                '/uds-auth/verify-code?qrCodeKey=' + encodeURIComponent(qrRef.current.key)
                + '&qrCodeValue=' + encodeURIComponent(qrRef.current.value)
                + '&loginClientIp=' + encodeURIComponent('127.0.0.1')
                + '&loginSystemCode=' + encodeURIComponent(loginSystemCode || config.loginSystemCode)
                + '&originSystemCode=' + encodeURIComponent(originSystemCode || config.originSystemCode || ''),
              )
              const result = await fetchJson('/uds-auth/qr-proxy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  qrCodeKey: qrRef.current.key,
                  qrCodeValue: qrRef.current.value,
                  loginClientIp: '127.0.0.1',
                  originSystemCode: originSystemCode || config.originSystemCode || '',
                  loginSystemCode: loginSystemCode || config.loginSystemCode,
                  verifyCode: verify.verifyCode,
                }),
              })
              const codeCode = result.code?.code || ''
              const boCode = result.bo?.code || ''
              if (codeCode === '0000' && boCode === '0000') {
                stopQr()
                const other = result.other || {}
                const empNo = other.account || other.empNo || ''
                const token = other.token || other.authValue || ''
                if (empNo && token) {
                  setCookie('PORTALSSOUser', empNo, 7)
                  setCookie('PORTALSSOCookie', token, 7)
                  try {
                    const info = await fetchJson(
                      '/uds-auth/user-info?empNo=' + encodeURIComponent(empNo)
                      + '&token=' + encodeURIComponent(token),
                    )
                    const ic = info?.code?.code ?? info?.code
                    const list = Array.isArray(info?.bo) ? info.bo
                      : Array.isArray(info?.bo?.rows) ? info.bo.rows
                        : Array.isArray(info?.bo?.list) ? info.bo.list
                          : []
                    if ((ic !== '0000' && ic !== 0 && ic !== '0') || !list.length) {
                      setQrStatus('\u7528\u6237\u4fe1\u606f\u67e5\u8be2\u5931\u8d25')
                      console.warn('[uds-auth] user-info after QR failed', info)
                      return
                    }
                  } catch (err) {
                    setQrStatus('\u7528\u6237\u4fe1\u606f\u67e5\u8be2\u5931\u8d25: ' + (err.message || err))
                    return
                  }
                  setQrStatus('\u767b\u5f55\u6210\u529f\uff01')
                  await refreshUser()
                  setOpen(false)
                } else {
                  setQrStatus('\u7f3a\u5c11 token\uff0c\u65e0\u6cd5\u5b8c\u6210\u6821\u9a8c')
                }
                return
              }
              if (codeCode === '0000' && boCode === '4002') {
                setQrStatus('\u7b49\u5f85\u626b\u7801...')
                return
              }
              if (codeCode === '0000' && boCode === '1002') {
                stopQr()
                setQrStatus('\u4e8c\u7ef4\u7801\u5df2\u8fc7\u671f\uff0c\u8bf7\u5237\u65b0')
                return
              }
              stopQr()
              setQrStatus(result.bo?.msg || boCode || '\u767b\u5f55\u5931\u8d25')
            } catch {
              setQrStatus('\u7f51\u7edc\u9519\u8bef...')
            }
          }, 2000)
        } catch (err) {
          setQrStatus(err.message || '\u751f\u6210\u4e8c\u7ef4\u7801\u5931\u8d25')
        }
      }, [config.loginSystemCode, config.originSystemCode, refreshUser, stopQr])

      const submitFallback = useCallback(async () => {
        setFbBusy(true)
        setFbErr('')
        try {
          await fetchJson('/uds-auth/api/fallback/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: fbUser.trim(), password: fbPass }),
          })
          setFbPass('')
          await refreshUser()
          setOpen(false)
        } catch (err) {
          setFbErr(err.data?.error || err.message || '\u767b\u5f55\u5931\u8d25')
        } finally {
          setFbBusy(false)
        }
      }, [fbUser, fbPass, refreshUser])

      useEffect(() => {
        refreshUser()
        fetchJson('/uds-auth/config.get')
          .then((data) => { if (data?.value) setConfig((prev) => ({ ...prev, ...data.value })) })
          .catch(() => {})
        fetchJson('/uds-auth/api/fallback/status')
          .then((st) => setFallbackEnabled(!!st.enabled))
          .catch(() => {})
        return () => { stopQr() }
      }, [refreshUser, stopQr])

      useEffect(() => {
        if (open && !user && loginMode === 'qr') startQr()
        if (!open || loginMode !== 'qr') stopQr()
      }, [open, user, loginMode, startQr, stopQr])

      useLayoutEffect(() => {
        if (!open) { setAnchor(null); return undefined }
        const place = () => {
          const rect = rootRef.current?.getBoundingClientRect()
          if (!rect) return
          setAnchor({
            left: Math.max(8, Math.min(rect.right - 300, window.innerWidth - 308)),
            top: Math.min(rect.bottom + 8, window.innerHeight - 80),
          })
        }
        place()
        window.addEventListener('resize', place)
        window.addEventListener('scroll', place, true)
        return () => {
          window.removeEventListener('resize', place)
          window.removeEventListener('scroll', place, true)
        }
      }, [open])

      useOutsideClose(rootRef, open, setOpen)

      const displayName = user
        ? (user.userName || user.name || ('\u7528\u6237' + user.empNo))
        : (loading ? '...' : '\u672a\u767b\u5f55')
      const initials = String(displayName).slice(0, 2).toUpperCase()
      const label = roleLabel(user?.role)
      const perms = user?.permissions || {}

      return h('div', {
        ref: rootRef,
        className: 'uds-auth-host',
        'data-uds-auth-host': 'header-utilities',
      },
      open && anchor && h('section', {
        className: 'uds-auth-panel',
        style: { left: anchor.left, top: anchor.top },
        'aria-label': 'UDS',
      },
      !user
        ? (loginMode === 'qr'
          ? h(React.Fragment, null,
            h('div', { className: 'uds-auth-info' },
              h('div', { className: 'uds-auth-info-name' }, '\u672a\u767b\u5f55'),
              h('div', { className: 'uds-auth-info-detail' }, '\u8bf7\u626b\u7801\u767b\u5f55'),
            ),
            h('div', { className: 'uds-auth-qr' },
              qrImg ? h('img', { src: qrImg, alt: 'QR' }) : null,
              h('div', { className: 'uds-auth-qr-status' }, qrStatus || '\u52a0\u8f7d\u4e2d...'),
              h('button', { type: 'button', className: 'uds-auth-btn uds-auth-btn-primary', onClick: startQr }, '\u5237\u65b0\u4e8c\u7ef4\u7801'),
            ),
            fallbackEnabled && h('button', {
              type: 'button',
              className: 'uds-auth-btn-link',
              onClick: () => { stopQr(); setLoginMode('fallback'); setFbErr('') },
            }, 'UAC \u4e0d\u53ef\u7528\uff1f\u5e94\u6025\u8d26\u53f7\u767b\u5f55'),
          )
          : h(React.Fragment, null,
            h('div', { className: 'uds-auth-info' },
              h('div', { className: 'uds-auth-info-name' }, '\u5e94\u6025\u767b\u5f55'),
              h('div', { className: 'uds-auth-info-detail' }, 'UAC / \u626b\u7801\u4e0d\u53ef\u7528\u65f6\u4f7f\u7528'),
            ),
            h('div', { className: 'uds-auth-fallback' },
              h('label', { htmlFor: 'uds-fb-user' }, '\u7528\u6237\u540d'),
              h('input', {
                id: 'uds-fb-user',
                value: fbUser,
                onChange: (e) => setFbUser(e.target.value),
                autoComplete: 'username',
              }),
              h('label', { htmlFor: 'uds-fb-pass' }, '\u5bc6\u7801'),
              h('input', {
                id: 'uds-fb-pass',
                type: 'password',
                value: fbPass,
                onChange: (e) => setFbPass(e.target.value),
                autoComplete: 'current-password',
                onKeyDown: (e) => { if (e.key === 'Enter') submitFallback() },
              }),
              fbErr && h('div', { className: 'uds-auth-settings-msg err' }, fbErr),
              h('p', { className: 'uds-auth-fallback-hint' },
                '\u9ed8\u8ba4\u7528\u6237\u540d administrator\uff1b\u5bc6\u7801\u5728\u300c\u8bbe\u7f6e \u2192 UDS \u8ba4\u8bc1\u300d\u7531\u8d85\u7ba1\u9884\u5148\u914d\u7f6e\u3002'),
              h('button', {
                type: 'button',
                className: 'uds-auth-btn uds-auth-btn-primary',
                style: { width: '100%', margin: '12px 0 0' },
                disabled: fbBusy,
                onClick: submitFallback,
              }, fbBusy ? '\u767b\u5f55\u4e2d...' : '\u767b\u5f55'),
            ),
            h('button', {
              type: 'button',
              className: 'uds-auth-btn-link',
              onClick: () => setLoginMode('qr'),
            }, '\u8fd4\u56de\u626b\u7801\u767b\u5f55'),
          ))
        : h(React.Fragment, null,
          h('div', { className: 'uds-auth-info' },
            h('div', { className: 'uds-auth-info-name' }, displayName),
            h('div', { className: 'uds-auth-info-detail' }, h('span', { className: 'uds-auth-info-detail-label' }, '\u5de5\u53f7'), user.empNo || '-'),
            h('div', { className: 'uds-auth-info-detail' }, h('span', { className: 'uds-auth-info-detail-label' }, '\u89d2\u8272'), label || user.role || '-'),
            user.department && h('div', { className: 'uds-auth-info-detail' }, h('span', { className: 'uds-auth-info-detail-label' }, '\u90e8\u95e8'), user.department),
          ),
          (perms.canManageUsers || perms.canAccessSettings) && h('button', {
            type: 'button', className: 'uds-auth-btn',
            onClick: () => { window.location.href = '/settings' },
          }, '\u8bbe\u7f6e / \u7528\u6237\u7ba1\u7406'),
          h('button', {
            type: 'button', className: 'uds-auth-btn uds-auth-btn-danger',
            onClick: async () => {
              try { await fetchJson('/uds-auth/api/logout', { method: 'POST' }) } catch { /* ignore */ }
              clearAuthCookies()
              window.location.reload()
            },
          }, '\u9000\u51fa\u767b\u5f55'),
        ),
      ),
      h('button', {
        type: 'button',
        className: 'uds-auth-badge' + (user ? '' : ' uds-auth-badge-unauth'),
        'aria-expanded': open,
        'aria-label': 'UDS',
        onClick: () => setOpen((v) => !v),
      },
      h('span', { className: 'uds-auth-avatar' }, user ? initials : '?'),
      h('span', { className: 'uds-auth-badge-label' }, displayName),
      label ? h('span', { className: 'uds-auth-role uds-auth-role-' + user.role }, label) : null,
      ),
      )
    }

    function apply(ctx) {
      ctx.effect(() => {
        const tag = document.createElement('style')
        tag.id = 'uds-auth-client-css'
        tag.setAttribute('data-plugin', name)
        tag.textContent = CSS
        document.head.appendChild(tag)
        return () => tag.remove()
      }, 'uds-auth: styles')

      // Same slot as @deepseek-ai/dsh-session-log-export (header.utilities); order -10 = left of it.
      ctx.slots.inject('conversation.session.header.utilities', () => ctx.slots.register({
        name: 'conversation.session.header.utilities',
        id: 'uds-auth-login',
        order: -10,
        label: 'UDS',
      }, AuthBadge))

      ctx.slots.inject('settings.section', () => ctx.slots.register({
        name: 'settings.section',
        id: 'uds-auth',
        order: 22,
        label: 'UDS \u8ba4\u8bc1',
        icon: 'users',
      }, AuthSettingsSection))
    }

    exports.name = name
    exports.inject = inject
    exports.apply = apply
    return module.exports
  },
})
