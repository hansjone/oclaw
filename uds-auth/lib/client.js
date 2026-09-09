/**
 * uds-auth browser half — sidebar.footer.action + force foot row with Settings (side by side) + settings.section.
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
    const inject = ['slots', 'locale']
    const PAGE_SIZE = 50
    const LOCALE_NS = 'uds-auth'

    /* uds-auth-i18n-begin — keep in sync with lib/i18n.js */
    const UDS_I18N_MESSAGES = {
  "zh": {
    "role.super_admin": "超级管理员",
    "role.admin": "管理员",
    "role.user": "普通用户",
    "role.fallback_admin": "应急管理员",
    "role.badge.super_admin": "超管",
    "role.badge.admin": "管理员",
    "role.badge.fallback_admin": "应急",
    "role.badge.user": "",
    "ui.settingsTitle": "UAC 认证",
    "ui.settingsIntro": "工号+token 双校验；UAC 挂死时用应急账号 administrator 密码登录。",
    "ui.loginRequiredPage": "请先登录后查看此页",
    "ui.roleHint": "当前角色：{role}。首位扫码登录且 roles.json 为空时会自动成为超管；普通 admin 需超管在「用户管理」提权后再扫码登录。应急账号 administrator 需超管先设密码，再在登录面板用账密登录。",
    "ui.deployConfig": "部署配置",
    "ui.userSearchUrl": "用户搜索 URL（token 校验）",
    "ui.workspaceRoot": "工作区根目录（空=$DSH_HOME/user-workspaces）",
    "ui.saveConfig": "保存配置",
    "ui.saving": "保存中...",
    "ui.configSaved": "配置已保存",
    "ui.saveFailed": "保存失败",
    "ui.fallbackTitle": "应急登录（UAC 不可用）",
    "ui.fallbackStatus": "状态：{status}。可在此改密或关闭。仅在扫码不可用时从登录面板切换。",
    "ui.enabled": "已启用",
    "ui.disabled": "未启用",
    "ui.fallbackPassword": "应急密码（至少 6 位）",
    "ui.saveFallbackPassword": "保存应急密码",
    "ui.fallbackPasswordSet": "应急密码已设置",
    "ui.confirmClearFallback": "确认清除应急密码？",
    "ui.clear": "清除",
    "ui.userManagement": "用户管理",
    "ui.searchEmpNo": "搜索工号",
    "ui.search": "搜索",
    "ui.loading": "加载中...",
    "ui.loadFailed": "加载失败",
    "ui.empNo": "工号",
    "ui.role": "角色",
    "ui.actions": "操作",
    "ui.noUsers": "暂无用户",
    "ui.delete": "删除",
    "ui.confirmDelete": "确认删除 {empNo}？",
    "ui.pager": "共 {total} 人，第 {page} / {totalPages} 页",
    "ui.prevPage": "上一页",
    "ui.nextPage": "下一页",
    "ui.add": "添加",
    "ui.department": "部门",
    "ui.notLoggedIn": "未登录",
    "ui.pleaseScan": "请使用 iCenter 扫码登录",
    "ui.refreshQr": "刷新二维码",
    "ui.fallbackLink": "UAC 不可用？应急账号登录",
    "ui.fallbackLogin": "应急登录",
    "ui.fallbackDetail": "UAC / 扫码不可用时使用",
    "ui.username": "用户名",
    "ui.password": "密码",
    "ui.login": "登录",
    "ui.loggingIn": "登录中...",
    "ui.backToQr": "返回扫码登录",
    "ui.logout": "退出登录",
    "ui.userPrefix": "用户",
    "ui.qrGenerating": "正在生成二维码...",
    "ui.qrScanPrompt": "请使用 iCenter 扫码登录...",
    "ui.userInfoFailed": "用户信息查询失败",
    "ui.loginSuccess": "登录成功！",
    "ui.missingToken": "缺少 token，无法完成校验",
    "ui.waitingScan": "等待扫码...",
    "ui.qrExpired": "二维码已失效",
    "ui.qrExpiredHint": "请刷新后重新扫描",
    "ui.loginFailed": "登录失败",
    "ui.networkError": "网络错误...",
    "ui.qrGenerateFailed": "生成二维码失败",
    "ui.cronLoginRequired": "登录后才能使用定时任务",
    "ui.workspaceCreateForbidden": "只有超级管理员可以创建工作区",
    "ui.workspaceLoginRequired": "登录后才能使用工作区",
    "err.not_logged_in": "未登录",
    "err.forbidden_settings": "当前账号无设置权限",
    "err.forbidden_manage_users": "只有超级管理员可以管理用户",
    "err.forbidden_list_users": "只有超级管理员可以查看用户列表",
    "err.forbidden_set_role": "只有超级管理员可以修改角色",
    "err.forbidden_add_user": "只有超级管理员可以添加用户",
    "err.forbidden_remove_user": "只有超级管理员可以删除用户",
    "err.forbidden_set_fallback": "只有超级管理员可以设置应急密码",
    "err.forbidden_clear_fallback": "只有超级管理员可以清除应急密码",
    "err.invalid_role_params": "参数错误: empNo 和 role 必填",
    "err.emp_no_required": "empNo 必填",
    "err.username_password_required": "用户名和密码必填",
    "err.invalid_credentials": "用户名或密码错误",
    "err.last_super_admin_demote": "系统至少需要 1 个超级管理员，不能降级最后一个",
    "err.last_super_admin_delete": "系统至少需要 1 个超级管理员，不能删除最后一个",
    "err.password_too_short": "密码至少 6 位",
    "err.config_not_ready": "配置未初始化",
    "err.request_failed": "请求失败",
    "err.method_not_allowed": "方法不允许",
    "err.missing_qr_params": "缺少 qrCodeKey 或 qrCodeValue",
    "err.missing_emp_token": "缺少 empNo 或 token",
    "err.user_search_failed": "用户搜索失败",
    "err.not_found": "未找到",
    "err.internal": "内部错误",
    "err.login_required_cron": "登录后才能使用定时任务",
    "err.login_required_session": "登录后才能访问会话",
    "err.login_required_create_session": "登录后才能创建会话",
    "err.login_required_workspace": "登录后才能使用工作区",
    "err.session_forbidden": "无权访问该会话",
    "err.session_workspace_only": "只能在自己的工作区创建会话",
    "err.workspace_path_only": "只能打开自己的工作区路径",
    "err.workspace_create_forbidden": "只有超级管理员可以创建工作区",
    "err.no_skill_credentials": "请先完成 UAC 扫码登录",
    "err.loopback_only_credentials": "agent-credentials 仅允许本机访问",
    "err.loopback_only_outbound": "outbound 仅允许本机访问",
    "err.url_required": "缺少 url",
    "err.invalid_url": "无效 url",
    "err.unsupported_protocol": "不支持的协议",
    "err.host_not_allowed": "主机不在白名单",
    "err.upstream_failed": "上游请求失败",
    "err.skill_credentials_not_ready": "skill 凭证未就绪",
    "err.outbound_not_ready": "outbound 未就绪",
    "ok.logged_out": "已退出登录",
    "ok.config_saved": "配置已保存",
    "ok.role_updated": "{empNo} 角色已更新为 {role}",
    "ok.user_added": "{empNo} 已添加为 {role}",
    "ok.user_removed": "{empNo} 已删除",
    "ok.fallback_password_set": "应急管理员密码已设置",
    "ok.fallback_password_cleared": "应急管理员密码已清除",
    "ok.fallback_login": "应急管理员登录成功"
  },
  "en": {
    "role.super_admin": "Super admin",
    "role.admin": "Admin",
    "role.user": "User",
    "role.fallback_admin": "Emergency admin",
    "role.badge.super_admin": "Super",
    "role.badge.admin": "Admin",
    "role.badge.fallback_admin": "Emergency",
    "role.badge.user": "",
    "ui.settingsTitle": "UAC Auth",
    "ui.settingsIntro": "EmpNo + token verification; when UAC is down, sign in with emergency account administrator.",
    "ui.loginRequiredPage": "Sign in to view this page",
    "ui.roleHint": "Current role: {role}. The first QR login with an empty roles.json becomes super admin; grant admin in User management then re-scan. Set the emergency password before using administrator on the login panel.",
    "ui.deployConfig": "Deploy config",
    "ui.userSearchUrl": "User search URL (token verify)",
    "ui.workspaceRoot": "Workspace root (empty=$DSH_HOME/user-workspaces)",
    "ui.saveConfig": "Save config",
    "ui.saving": "Saving...",
    "ui.configSaved": "Config saved",
    "ui.saveFailed": "Save failed",
    "ui.fallbackTitle": "Emergency login (UAC unavailable)",
    "ui.fallbackStatus": "Status: {status}. Change or disable here. Switch from the login panel only when QR is unavailable.",
    "ui.enabled": "Enabled",
    "ui.disabled": "Disabled",
    "ui.fallbackPassword": "Emergency password (min 6 chars)",
    "ui.saveFallbackPassword": "Save emergency password",
    "ui.fallbackPasswordSet": "Emergency password set",
    "ui.confirmClearFallback": "Clear emergency password?",
    "ui.clear": "Clear",
    "ui.userManagement": "User management",
    "ui.searchEmpNo": "Search empNo",
    "ui.search": "Search",
    "ui.loading": "Loading...",
    "ui.loadFailed": "Load failed",
    "ui.empNo": "EmpNo",
    "ui.role": "Role",
    "ui.actions": "Actions",
    "ui.noUsers": "No users",
    "ui.delete": "Delete",
    "ui.confirmDelete": "Delete {empNo}?",
    "ui.pager": "{total} users, page {page} / {totalPages}",
    "ui.prevPage": "Previous",
    "ui.nextPage": "Next",
    "ui.add": "Add",
    "ui.department": "Department",
    "ui.notLoggedIn": "Not signed in",
    "ui.pleaseScan": "Scan with iCenter to sign in",
    "ui.refreshQr": "Refresh QR",
    "ui.fallbackLink": "UAC down? Emergency account",
    "ui.fallbackLogin": "Emergency login",
    "ui.fallbackDetail": "Use when UAC / QR is unavailable",
    "ui.username": "Username",
    "ui.password": "Password",
    "ui.login": "Sign in",
    "ui.loggingIn": "Signing in...",
    "ui.backToQr": "Back to QR login",
    "ui.logout": "Sign out",
    "ui.userPrefix": "User",
    "ui.qrGenerating": "Generating QR...",
    "ui.qrScanPrompt": "Scan with iCenter to sign in...",
    "ui.userInfoFailed": "User info lookup failed",
    "ui.loginSuccess": "Signed in!",
    "ui.missingToken": "Missing token; cannot verify",
    "ui.waitingScan": "Waiting for scan...",
    "ui.qrExpired": "QR code expired",
    "ui.qrExpiredHint": "Refresh and scan again",
    "ui.loginFailed": "Sign-in failed",
    "ui.networkError": "Network error...",
    "ui.qrGenerateFailed": "Failed to generate QR",
    "ui.cronLoginRequired": "Sign in to use scheduled tasks",
    "ui.workspaceCreateForbidden": "Only super admins can create workspaces",
    "ui.workspaceLoginRequired": "Sign in to use workspaces",
    "err.not_logged_in": "Not signed in",
    "err.forbidden_settings": "No settings permission",
    "err.forbidden_manage_users": "Only super admins can manage users",
    "err.forbidden_list_users": "Only super admins can list users",
    "err.forbidden_set_role": "Only super admins can change roles",
    "err.forbidden_add_user": "Only super admins can add users",
    "err.forbidden_remove_user": "Only super admins can remove users",
    "err.forbidden_set_fallback": "Only super admins can set the emergency password",
    "err.forbidden_clear_fallback": "Only super admins can clear the emergency password",
    "err.invalid_role_params": "Invalid params: empNo and role required",
    "err.emp_no_required": "empNo required",
    "err.username_password_required": "Username and password required",
    "err.invalid_credentials": "Invalid username or password",
    "err.last_super_admin_demote": "At least one super admin is required; cannot demote the last one",
    "err.last_super_admin_delete": "At least one super admin is required; cannot delete the last one",
    "err.password_too_short": "Password must be at least 6 characters",
    "err.config_not_ready": "Config not initialized",
    "err.request_failed": "Request failed",
    "err.method_not_allowed": "Method not allowed",
    "err.missing_qr_params": "Missing qrCodeKey or qrCodeValue",
    "err.missing_emp_token": "Missing empNo or token",
    "err.user_search_failed": "User search failed",
    "err.not_found": "Not found",
    "err.internal": "Internal error",
    "err.login_required_cron": "Sign in to use scheduled tasks",
    "err.login_required_session": "Sign in to access sessions",
    "err.login_required_create_session": "Sign in to create a session",
    "err.login_required_workspace": "Sign in to use workspaces",
    "err.session_forbidden": "No access to this session",
    "err.session_workspace_only": "Sessions can only be created in your own workspace",
    "err.workspace_path_only": "You can only open your own workspace path",
    "err.workspace_create_forbidden": "Only super admins can create workspaces",
    "err.no_skill_credentials": "Complete UAC QR sign-in first",
    "err.loopback_only_credentials": "agent-credentials is loopback-only",
    "err.loopback_only_outbound": "outbound is loopback-only",
    "err.url_required": "url required",
    "err.invalid_url": "invalid url",
    "err.unsupported_protocol": "unsupported protocol",
    "err.host_not_allowed": "host not allowed",
    "err.upstream_failed": "upstream failed",
    "err.skill_credentials_not_ready": "skill credentials not ready",
    "err.outbound_not_ready": "outbound not ready",
    "ok.logged_out": "Signed out",
    "ok.config_saved": "Config saved",
    "ok.role_updated": "{empNo} role updated to {role}",
    "ok.user_added": "{empNo} added as {role}",
    "ok.user_removed": "{empNo} removed",
    "ok.fallback_password_set": "Emergency admin password set",
    "ok.fallback_password_cleared": "Emergency admin password cleared",
    "ok.fallback_login": "Emergency admin signed in"
  }
}
    const UDS_HOST_ARIA = {
  "addWorkspace": [
    "添加工作区",
    "Add workspace"
  ],
  "chooseWorkspace": [
    "选择工作区",
    "Choose workspace"
  ],
  "sessions": [
    "会话",
    "Sessions"
  ]
}
    /** Prefer DSH host locale over portal SSO language cookies. */
    let localeHost = null
    let translate = null
    function normalizeLocale(lang) {
      const raw = String(lang || '').trim().toLowerCase()
      if (raw.startsWith('zh')) return 'zh'
      return 'en'
    }
    function getUiLocale() {
      try {
        const snap = typeof localeHost?.locale?.getSnapshot === 'function'
          ? localeHost.locale.getSnapshot()
          : null
        const raw = snap?.active
          || snap?.locale
          || snap?.preference
          || localeHost?.locale?.active
          || (document.documentElement && document.documentElement.lang)
          || (typeof navigator !== 'undefined' && (navigator.language || navigator.userLanguage))
          || ''
        return normalizeLocale(raw)
      } catch {
        return 'en'
      }
    }
    function applyVars(text, vars) {
      let out = String(text)
      if (vars && typeof vars === 'object') {
        for (const k of Object.keys(vars)) {
          out = out.split('{' + k + '}').join(String(vars[k]))
        }
      }
      return out
    }
    function t(key, vars) {
      if (typeof translate === 'function') {
        try {
          const out = translate(key, vars)
          if (out != null && out !== key) return applyVars(out, vars)
        } catch { /* fall through */ }
      }
      const loc = getUiLocale()
      const table = UDS_I18N_MESSAGES[loc] || UDS_I18N_MESSAGES.zh
      const text = (table && table[key])
        || (UDS_I18N_MESSAGES.en && UDS_I18N_MESSAGES.en[key])
        || (UDS_I18N_MESSAGES.zh && UDS_I18N_MESSAGES.zh[key])
        || key
      return applyVars(text, vars)
    }
    function makeTranslator(ctx) {
      if (typeof ctx?.locale?.bind === 'function') {
        try {
          const bound = ctx.locale.bind(LOCALE_NS)
          if (typeof bound === 'function') {
            return (key, params) => {
              try {
                const out = bound(key, params)
                if (out != null && out !== key) return out
              } catch { /* fall through */ }
              const dict = getUiLocale() === 'zh' ? UDS_I18N_MESSAGES.zh : UDS_I18N_MESSAGES.en
              return (dict && dict[key]) || UDS_I18N_MESSAGES.en[key] || UDS_I18N_MESSAGES.zh[key] || key
            }
          }
        } catch { /* fall through */ }
      }
      return (key) => {
        const dict = getUiLocale() === 'zh' ? UDS_I18N_MESSAGES.zh : UDS_I18N_MESSAGES.en
        return (dict && dict[key]) || UDS_I18N_MESSAGES.en[key] || UDS_I18N_MESSAGES.zh[key] || key
      }
    }
    function roleLabel(role) {
      return t('role.badge.' + String(role || 'user')) || t('role.' + String(role || 'user'))
    }
    function apiMessage(err) {
      const data = err && err.data
      const code = data && data.error
      if (code) {
        const key = String(code).startsWith('err.') ? code : 'err.' + code
        const translated = t(key)
        if (translated && translated !== key) return translated
      }
      return (data && (data.message || data.error)) || (err && err.message) || t('err.request_failed')
    }
    function hostAriaList(key) {
      return (UDS_HOST_ARIA && UDS_HOST_ARIA[key]) || []
    }
    function hostButtonAriaSel(key) {
      return hostAriaList(key).map((l) => 'button[aria-label="' + l + '"]').join(',')
    }
    function hostAriaSel(key) {
      return hostAriaList(key).map((l) => '[aria-label="' + l + '"]').join(',')
    }
    /* uds-auth-i18n-end */


    const CSS = [
      '.uds-auth-host{position:relative;display:inline-flex;align-items:center;height:32px;margin:0;flex-shrink:0;pointer-events:auto}.uds-auth-host.is-rail{justify-content:center;width:100%}[data-uds-auth-foot="row"]{display:flex!important;flex-direction:row!important;align-items:center!important;gap:8px;width:100%}[data-uds-auth-foot="row"]>*:nth-child(1){order:2;flex:none!important;width:auto!important;min-width:0;margin-left:auto!important}[data-uds-auth-foot="row"]>*:nth-child(2){order:1;flex:none!important;width:auto!important;min-width:0}',
      'html[data-uds-can-settings="0"] [data-uds-auth-foot="row"]>*:not(:has([data-uds-auth-host])){display:none!important}html[data-uds-can-create-ws="0"] button[aria-label="添加工作区"],html[data-uds-can-create-ws="0"] button[aria-label="Add workspace"]{display:none!important}html[data-uds-logged-in="0"] [role="tree"][aria-label="会话"],html[data-uds-logged-in="0"] [role="tree"][aria-label="Sessions"],html[data-uds-logged-in="0"] [class*="WorkspaceBrowser"],html[data-uds-logged-in="0"] [class*="workspaceBrowser"],html[data-uds-logged-in="0"] .dsh-ct-entry,html[data-uds-logged-in="0"] .dsh-ct-region,html[data-uds-logged-in="0"] .dsh-ct-main,html[data-uds-logged-in="0"] [data-dsh-ct-mode="on"] .dsh-ct-region{display:none!important}html[data-uds-can-create-ws="0"] button[aria-label="选择工作区"],html[data-uds-can-create-ws="0"] button[aria-label="Choose workspace"],html[data-uds-can-create-ws="0"] [aria-label="选择工作区"],html[data-uds-can-create-ws="0"] [aria-label="Choose workspace"]{display:none!important}html[data-uds-logged-in="0"] [class*="cardWorkspaceTrigger"],html[data-uds-logged-in="0"] [data-composer-card][class*="cardWorkspaceTrigger"]{pointer-events:none!important;opacity:.45!important;cursor:not-allowed!important}/* uds-anon-hide-workspaces *//* uds-anon-hide-conversation:removed */html[data-uds-logged-in="0"] [class*="WorkspaceBrowser"],html[data-uds-logged-in="0"] [class*="workspaceBrowser"],html[data-uds-logged-in="0"] [class*="workspaceRow"],html[data-uds-logged-in="0"] [class*="WorkspaceRow"]{display:none!important}',
      /* uds-session-only-sidebar */
      'html[data-uds-can-create-ws="0"][data-uds-logged-in="1"] [class*="projectRow"]:not([class*="dsh-ct-project"]),html[data-uds-can-create-ws="0"][data-uds-logged-in="1"] [class*="ProjectRow"]:not([class*="dsh-ct-project"]){display:none!important}',
      '.uds-auth-badge{display:inline-flex;align-items:center;justify-content:flex-start;gap:0;max-width:min(160px,42vw);min-width:0;height:32px;padding:0 8px;box-sizing:border-box;border:none;border-radius:8px;background:transparent;color:var(--dsw-alias-label-primary);font-family:inherit;font-size:13px;font-weight:400;line-height:20px;cursor:pointer;overflow:hidden}',
      '.uds-auth-badge:hover{background:var(--dsw-alias-interactive-bg-hover)}',
      '.uds-auth-host.is-rail .uds-auth-badge{width:auto;max-width:100%;height:32px;padding:0 6px;border-radius:8px}',
      '.uds-auth-badge-unauth{color:var(--dsw-alias-label-tertiary,#8f959e)}',
      '.uds-auth-avatar{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;flex:none;font-size:10px;line-height:1;color:var(--dsw-alias-label-secondary,#646a73);background:transparent;border:none}',
      '.uds-auth-badge-unauth .uds-auth-avatar{background:var(--dsw-alias-bg-module-platform,rgba(242,243,245,1));color:var(--dsw-alias-label-tertiary,#8f959e)}',
      '.uds-auth-badge-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.uds-auth-role{font-size:10px;padding:1px 6px;border-radius:10px;font-weight:600;flex-shrink:0}',
      '.uds-auth-role-super_admin{background:rgba(213,73,65,.12);color:var(--dsw-alias-state-error-primary,#d54941)}',
      '.uds-auth-role-admin{background:rgba(217,119,6,.12);color:var(--dsw-alias-state-warn-primary,#d97706)}',
      '.uds-auth-role-fallback_admin{background:rgba(51,112,255,.12);color:var(--dsw-alias-state-business-primary,#3370ff)}',
      '.uds-auth-panel{position:fixed;z-index:1200;width:min(300px,calc(100vw - 24px));max-height:min(70vh,560px);overflow:auto;top:auto;background:var(--dsw-alias-bg-layer-1,#fff);border-radius:8px;border:1px solid var(--dsw-alias-border-l2,#dee0e3);box-shadow:0 8px 28px rgba(0,0,0,.12)}',
      '.uds-auth-info{padding:14px 16px;border-bottom:1px solid var(--dsw-alias-border-l1,#eef0f3)}',
      '.uds-auth-info-name{font-weight:600;margin-bottom:4px;color:var(--dsw-alias-label-primary,#1f2329);font-size:14px}',
      '.uds-auth-info-detail{font-size:12px;color:var(--dsw-alias-label-secondary,#646a73);margin-top:2px;display:flex;justify-content:space-between;gap:8px}',
      '.uds-auth-info-detail-label{color:var(--dsw-alias-label-tertiary,#8f959e)}',
      '.uds-auth-qr{padding:16px;text-align:center}',
      '.uds-auth-qr-frame{position:relative;width:160px;height:160px;margin:0 auto;background:var(--dsw-alias-bg-layer-1,#fff);box-sizing:border-box;border:1px solid var(--dsw-alias-border-l2,#dee0e3);border-radius:4px;overflow:hidden}',
      '.uds-auth-qr-frame img{display:block;width:100%;height:100%;object-fit:contain}',
      '.uds-auth-qr-frame.is-expired img{opacity:.18;filter:grayscale(1)}',
      '.uds-auth-qr-overlay{position:absolute;inset:0;z-index:3;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px;box-sizing:border-box;background:color-mix(in srgb, var(--dsw-alias-bg-layer-1,#fff) 82%, transparent)}',
      '.uds-auth-qr-overlay-title{font-size:15px;font-weight:700;line-height:1.3;color:var(--dsw-alias-label-primary,#1f2329)}',
      '.uds-auth-qr-overlay-hint{font-size:12px;line-height:1.3;color:var(--dsw-alias-label-secondary,#646a73);margin-bottom:2px}',
      '.uds-auth-qr-refresh{width:40px;height:40px;border:none;border-radius:50%;background:var(--dsw-alias-state-business-primary,#3370ff);color:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;padding:0;flex:none}',
      '.uds-auth-qr-refresh:hover{opacity:.9}',
      '.uds-auth-qr-refresh:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary,#3370ff);outline-offset:2px}',
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
      const names = ['PORTALSSOUser', 'PORTALSSOCookie', 'ZTEDPGSSOUser', 'ZTEDPGSSOCookie', 'UDS_FALLBACK_USER', 'UDS_FALLBACK_UI']
      for (const key of names) {
        // Match both Secure and non-Secure variants; HttpOnly ones need server clear.
        document.cookie = encodeURIComponent(key) + '=; Max-Age=0; Path=/; SameSite=Lax'
        document.cookie = encodeURIComponent(key) + '=; Max-Age=0; Path=/; SameSite=Lax; Secure'
        document.cookie = encodeURIComponent(key) + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
      }
    }

    function getEmpNo() {
      return getCookie('PORTALSSOUser') || getCookie('ZTEDPGSSOUser') || getCookie('UDS_FALLBACK_USER') || getCookie('UDS_FALLBACK_UI') || null
    }

    /** Prefer /api/me-driven attr: fallback login cookie is HttpOnly and invisible to document.cookie. */
    function isUdsAuthReady() {
      return document.documentElement.getAttribute('data-uds-auth-ready') === '1'
    }

    /** True only after /api/me confirmed a user — portal empNo cookie alone does not count. */
    function isLoggedInInUi() {
      return document.documentElement.getAttribute('data-uds-logged-in') === '1'
    }

    function clearSessionIfAnonymous(sessions) {
      // Wait for first /api/me so we do not wipe a real session during bootstrap.
      if (!isUdsAuthReady()) return
      if (isLoggedInInUi()) return
      try {
        if (sessions && typeof sessions.clear === 'function') sessions.clear()
      } catch { /* ignore */ }
      try {
        window.localStorage.removeItem('dsh.sessions.current')
      } catch { /* ignore */ }
      // Navigation may auto-reopen; clear again on next ticks while still anonymous.
      try {
        const snap = sessions && sessions.list && typeof sessions.list.getSnapshot === 'function'
          ? sessions.list.getSnapshot()
          : null
        if (snap && snap.current != null) {
          setTimeout(() => {
            if (isLoggedInInUi()) return
            try { sessions.clear() } catch { /* ignore */ }
            try { window.localStorage.removeItem('dsh.sessions.current') } catch { /* ignore */ }
          }, 0)
          setTimeout(() => {
            if (isLoggedInInUi()) return
            try { sessions.clear() } catch { /* ignore */ }
          }, 350)
        }
      } catch { /* ignore */ }
    }

    const VIEW_STORE_KEY = 'dsh.workspace.view.v5'
    const FORCED_FLAT_KEY = 'uds-auth-forced-flat'

    function readViewState() {
      try {
        const raw = window.localStorage.getItem(VIEW_STORE_KEY)
        const state = raw ? JSON.parse(raw) : null
        if (state && typeof state === 'object') return state
      } catch { /* ignore */ }
      return {
        groupBy: 'workspace',
        orderBy: 'updated',
        groupExpansion: {},
        sessionOrderByAccount: {},
        sessionUpdatedAtByAccount: {},
      }
    }

    function writeViewState(state) {
      window.localStorage.setItem(VIEW_STORE_KEY, JSON.stringify(state))
    }

    /** user/admin only — wait until /api/me set can-create-ws explicitly to 0. */
    function ensureFlatSessionSidebar() {
      try {
        const root = document.documentElement
        if (root.getAttribute('data-uds-auth-ready') !== '1') return false
        if (root.getAttribute('data-uds-logged-in') !== '1') return false
        // Must be explicit 0 — missing/default must not force flat for supers.
        if (root.getAttribute('data-uds-can-create-ws') !== '0') return false
        const state = readViewState()
        if (state.groupBy === 'flat') {
          try { window.localStorage.setItem(FORCED_FLAT_KEY, '1') } catch { /* ignore */ }
          return false
        }
        state.groupBy = 'flat'
        writeViewState(state)
        try { window.localStorage.setItem(FORCED_FLAT_KEY, '1') } catch { /* ignore */ }
        return true
      } catch {
        return false
      }
    }

    /** super/fallback: restore workspace partitions after a forced flat. */
    function ensureWorkspaceGroupedSidebar() {
      try {
        const root = document.documentElement
        if (root.getAttribute('data-uds-auth-ready') !== '1') return false
        if (root.getAttribute('data-uds-logged-in') !== '1') return false
        if (root.getAttribute('data-uds-can-create-ws') !== '1') return false
        const state = readViewState()
        if (state.groupBy === 'workspace') {
          try { window.localStorage.removeItem(FORCED_FLAT_KEY) } catch { /* ignore */ }
          return false
        }
        state.groupBy = 'workspace'
        writeViewState(state)
        try { window.localStorage.removeItem(FORCED_FLAT_KEY) } catch { /* ignore */ }
        return true
      } catch {
        return false
      }
    }

    function expandHiddenWorkspaceGroups() {
      try {
        if (document.documentElement.getAttribute('data-uds-auth-ready') !== '1') return
        if (document.documentElement.getAttribute('data-uds-logged-in') !== '1') return
        if (document.documentElement.getAttribute('data-uds-can-create-ws') !== '0') return
        document.querySelectorAll('[class*="projectRow"][aria-expanded="false"]:not([class*="dsh-ct-project"])').forEach((el) => {
          try { el.click() } catch { /* ignore */ }
        })
      } catch { /* ignore */ }
    }

function reloadAfterLogin() {
      // Login Set-Cookie must land before WS upgrade — hard reload is required.
      try { ensureFlatSessionSidebar() } catch { /* ignore */ }
      try { window.location.reload() } catch { /* ignore */ }
    }

    /** Soft WS reconnect (logout / auth flip). Prefer this over full reload. */
    function softReconnectAuth() {
      try {
        if (typeof window.__udsAuthReconnect === 'function') {
          window.__udsAuthReconnect()
          return
        }
      } catch { /* fall through */ }
      try { window.location.reload() } catch { /* ignore */ }
    }

    // Back-compat alias used by older call sites in this file.
    function reconnectAfterLogin() {
      reloadAfterLogin()
    }

    function getAuthToken() {
      return getCookie('PORTALSSOCookie') || getCookie('ZTEDPGSSOCookie') || null
    }

    async function fetchJson(url, options) {
      const res = await fetch(url, options)
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        const err = new Error(data.message || data.error || res.statusText || t('err.request_failed'))
        err.status = res.status
        err.data = data
        throw err
      }
      return data
    }

    function useLocaleTick() {
      const [tick, setTick] = useState(0)
      useEffect(() => {
        const bump = () => setTick((n) => n + 1)
        const offs = []
        try {
          const off = localeHost?.on?.('locale/change', bump)
          if (typeof off === 'function') offs.push(off)
        } catch { /* ignore */ }
        try {
          const off = localeHost?.locale?.subscribe?.(bump)
          if (typeof off === 'function') offs.push(off)
        } catch { /* ignore */ }
        let last = typeof document !== 'undefined' ? document.documentElement?.lang : ''
        const timer = setInterval(() => {
          const next = document.documentElement?.lang || ''
          if (next !== last) {
            last = next
            bump()
          }
        }, 800)
        return () => {
          for (const off of offs) {
            try { off() } catch { /* ignore */ }
          }
          clearInterval(timer)
        }
      }, [])
      return tick
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
      useLocaleTick()
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
          setError(apiMessage(err) || t('ui.loadFailed'))
          setUsers([])
        } finally {
          setLoading(false)
        }
      }, [page, q])

      useEffect(() => { reload() }, [reload])

      return h('div', { className: 'uds-auth-settings-card' },
        h('h3', null, t('ui.userManagement')),
        h('div', { className: 'uds-auth-search' },
          h('input', {
            value: qDraft,
            placeholder: t('ui.searchEmpNo'),
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
          }, t('ui.search')),
        ),
        error && h('div', { className: 'uds-auth-settings-msg err', role: 'alert' }, error),
        loading
          ? h('div', { className: 'uds-auth-settings-empty' }, t('ui.loading'))
          : h('table', { className: 'uds-auth-table' },
            h('thead', null, h('tr', null, h('th', null, t('ui.empNo')), h('th', null, t('ui.role')), h('th', null, t('ui.actions')))),
            h('tbody', null, users.length === 0
              ? h('tr', null, h('td', { colSpan: 3 }, t('ui.noUsers')))
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
                      } catch (err) { window.alert(apiMessage(err)) }
                    },
                  },
                  h('option', { value: 'user' }, t('role.user')),
                  h('option', { value: 'admin' }, t('role.admin')),
                  h('option', { value: 'super_admin' }, t('role.super_admin')),
                  ),
                ),
                h('td', null,
                  h('button', {
                    type: 'button', className: 'uds-auth-del',
                    onClick: async () => {
                      if (!window.confirm(t('ui.confirmDelete', { empNo: u.empNo }))) return
                      try {
                        await fetchJson('/uds-auth/api/users/delete', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ empNo: u.empNo }),
                        })
                        reload()
                      } catch (err) { window.alert(apiMessage(err)) }
                    },
                  }, t('ui.delete')),
                ),
              )),
            ),
          ),
        h('div', { className: 'uds-auth-pager' },
          h('span', null, t('ui.pager', { total, page, totalPages })),
          h('span', null,
            h('button', {
              type: 'button', disabled: page <= 1 || loading,
              onClick: () => setPage((p) => Math.max(1, p - 1)),
            }, t('ui.prevPage')),
            ' ',
            h('button', {
              type: 'button', disabled: page >= totalPages || loading,
              onClick: () => setPage((p) => p + 1),
            }, t('ui.nextPage')),
          ),
        ),
        h('div', { className: 'uds-auth-add' },
          h('input', { value: newEmpNo, placeholder: t('ui.empNo'), onChange: (e) => setNewEmpNo(e.target.value) }),
          h('select', { value: newRole, onChange: (e) => setNewRole(e.target.value) },
            h('option', { value: 'user' }, t('role.user')),
            h('option', { value: 'admin' }, t('role.admin')),
            h('option', { value: 'super_admin' }, t('role.super_admin')),
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
              } catch (err) { window.alert(apiMessage(err)) }
            },
          }, t('ui.add')),
        ),
      )
    }

    function AuthSettingsSection() {
      useLocaleTick()
      const [me, setMe] = useState(null)
      const [form, setForm] = useState({
        uacBaseUrl: '',
        userSearchUrl: '',
        loginSystemCode: '',
        originSystemCode: '',
        workspaceRoot: '',
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
          setMsg(t('ui.configSaved'))
        } catch (err) {
          setMsgKind('err')
          setMsg(apiMessage(err) || t('ui.saveFailed'))
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

      return h('section', { className: 'uds-auth-settings', 'aria-label': t('ui.settingsTitle') },
        h('header', null,
          h('h2', null, t('ui.settingsTitle')),
          h('p', { className: 'uds-auth-settings-intro' }, t('ui.settingsIntro')),
        ),
        !me && h('div', { className: 'uds-auth-settings-empty' }, t('ui.loginRequiredPage')),
        me && !canSettings && !canManage && h('div', { className: 'uds-auth-settings-empty' },
          t('ui.roleHint', { role: me.role || 'user' })
        ),
        canSettings && h('div', { className: 'uds-auth-settings-card' },
          h('h3', null, t('ui.deployConfig')),
          field('uacBaseUrl', 'UAC Base URL'),
          field('userSearchUrl', t('ui.userSearchUrl')),
          field('loginSystemCode', 'loginSystemCode'),
          field('originSystemCode', 'originSystemCode'),
          field('workspaceRoot', t('ui.workspaceRoot')),
          h('div', { className: 'uds-auth-settings-actions' },
            h('button', {
              type: 'button',
              className: 'uds-auth-btn uds-auth-btn-primary',
              style: { width: 'auto', margin: 0 },
              disabled: busy,
              onClick: saveConfig,
            }, busy ? t('ui.saving') : t('ui.saveConfig')),
            msg && h('span', { className: 'uds-auth-settings-msg ' + msgKind }, msg),
          ),
        ),
        canManage && h('div', { className: 'uds-auth-settings-card' },
          h('h3', null, t('ui.fallbackTitle')),
          h('p', { className: 'uds-auth-settings-intro' },
            t('ui.fallbackStatus', { status: fallbackEnabled ? t('ui.enabled') : t('ui.disabled') })),
          h('div', { className: 'uds-auth-settings-field' },
            h('label', { htmlFor: 'uds-auth-fallback-pwd' }, t('ui.fallbackPassword')),
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
                  window.alert(t('ui.fallbackPasswordSet'))
                } catch (err) { window.alert(apiMessage(err)) }
              },
            }, t('ui.saveFallbackPassword')),
            fallbackEnabled && h('button', {
              type: 'button',
              className: 'uds-auth-btn uds-auth-btn-danger',
              style: { width: 'auto', margin: 0 },
              onClick: async () => {
                if (!window.confirm(t('ui.confirmClearFallback'))) return
                try {
                  await fetchJson('/uds-auth/api/fallback/clear', { method: 'POST' })
                  setFallbackEnabled(false)
                } catch (err) { window.alert(apiMessage(err)) }
              },
            }, t('ui.clear')),
          ),
        ),
        canManage && h(UserManagementPanel, null),
      )
    }

    function AuthBadge(props = {}) {
      useLocaleTick()
      const wide = props.wide !== false
      const rootRef = useRef(null)
      useLayoutEffect(() => {
        const host = rootRef.current
        if (!host) return undefined
        // Climb to the official footArea that holds footer.action + sidebar.settings.
        let footArea = null
        for (let el = host.parentElement; el && el !== document.body; el = el.parentElement) {
          if (el.childElementCount < 2) continue
          const mine = [...el.children].some((c) => c.contains(host))
          const other = [...el.children].some((c) => !c.contains(host))
          if (mine && other) { footArea = el; break }
        }
        if (!footArea) return undefined
        footArea.setAttribute('data-uds-auth-foot', 'row')
        return () => { footArea.removeAttribute('data-uds-auth-foot') }
      }, [])
      const [open, setOpen] = useState(false)
      const [anchor, setAnchor] = useState(null)
      const [user, setUser] = useState(null)
      

      const [loading, setLoading] = useState(true)
      const [config, setConfig] = useState({ loginSystemCode: '100000455558', originSystemCode: '' })
      const [qrStatus, setQrStatus] = useState('')
      const [qrImg, setQrImg] = useState('')
      const [qrExpired, setQrExpired] = useState(false)
      const [qrFailed, setQrFailed] = useState(false)
      const [loginMode, setLoginMode] = useState('qr')
      const [fallbackEnabled, setFallbackEnabled] = useState(false)
      const [fbUser, setFbUser] = useState('administrator')
      const [fbPass, setFbPass] = useState('')
      const [fbBusy, setFbBusy] = useState(false)
      const [fbErr, setFbErr] = useState('')
      const qrRef = useRef({ key: null, value: null, timer: null, timeout: null, deadline: 0 })
      const QR_TIMEOUT_MS = 60 * 1000

      useEffect(() => {
        const perms = user?.permissions || {}
        const canSettings = user ? !!perms.canAccessSettings : false
        const canCreateWs = user ? !!perms.canCreateWorkspace : false
        const prev = document.documentElement.getAttribute('data-uds-logged-in')
        document.documentElement.setAttribute('data-uds-logged-in', user ? '1' : '0')
        document.documentElement.setAttribute('data-uds-can-settings', canSettings ? '1' : '0')
        document.documentElement.setAttribute('data-uds-can-create-ws', canCreateWs ? '1' : '0')
        // Drop stale remote.mux identity after logout so workspace names disappear.
        if (prev === '1' && !user) {
          clearSessionIfAnonymous(window.__udsAuthSessions)
          try { softReconnectAuth() } catch { /* ignore */ }
        }
        return () => {
          // Keep locked while remounting; do not leave attrs missing (CSS/click lock needs "0").
          document.documentElement.setAttribute('data-uds-logged-in', '0')
          document.documentElement.setAttribute('data-uds-can-settings', '0')
          document.documentElement.setAttribute('data-uds-can-create-ws', '0')
        }
      }, [user]) /* uds-auth: logout-reconnect-on-null */

      const stopQr = useCallback(() => {
        if (qrRef.current.timer) { clearInterval(qrRef.current.timer); qrRef.current.timer = null }
        if (qrRef.current.timeout) { clearTimeout(qrRef.current.timeout); qrRef.current.timeout = null }
        qrRef.current.key = null
        qrRef.current.value = null
        qrRef.current.deadline = 0
      }, [])

      const markQrExpired = useCallback(() => {
        stopQr()
        setQrFailed(false)
        setQrExpired(true)
        setQrStatus(t('ui.qrExpired'))
      }, [stopQr])

      const markQrFailed = useCallback((message) => {
        stopQr()
        setQrExpired(false)
        setQrFailed(true)
        setQrImg('')
        setQrStatus(message || t('ui.qrGenerateFailed'))
      }, [stopQr])

      const refreshUser = useCallback(async () => {
        try {
          const me = await fetchJson('/uds-auth/api/me')
          if (!me?.authenticated || !me?.data) {
            setUser(null)
            window.dispatchEvent(new Event('uds-auth-changed'))
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
          window.dispatchEvent(new Event('uds-auth-changed'))
        } catch {
          setUser(null)
          window.dispatchEvent(new Event('uds-auth-changed'))
        } finally {
          document.documentElement.setAttribute('data-uds-auth-ready', '1')
          setLoading(false)
        }
      }, [])

      const startQr = useCallback(async () => {
        stopQr()
        setQrExpired(false)
        setQrFailed(false)
        setQrStatus(t('ui.qrGenerating'))
        setQrImg('')
        try {
          const started = await fetchJson('/uds-auth/qr-start')
          const { qrCodeStr, qrCodeKey, qrCodeValue, loginSystemCode, originSystemCode } = started
          qrRef.current.key = qrCodeKey
          qrRef.current.value = qrCodeValue
          qrRef.current.deadline = Date.now() + QR_TIMEOUT_MS
          setQrImg('/uds-auth/qr?data=' + encodeURIComponent(qrCodeStr))
          setQrStatus(t('ui.qrScanPrompt'))
          qrRef.current.timeout = setTimeout(() => {
            if (!qrRef.current.key) return
            markQrExpired()
          }, QR_TIMEOUT_MS)
          qrRef.current.timer = setInterval(async () => {
            if (!qrRef.current.key) return
            if (qrRef.current.deadline && Date.now() >= qrRef.current.deadline) {
              markQrExpired()
              return
            }
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
                setQrExpired(false)
                setQrFailed(false)
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
                      setQrStatus(t('ui.userInfoFailed'))
                      console.warn('[uds-auth] user-info after QR failed', info)
                      return
                    }
                  } catch (err) {
                    setQrStatus(t('ui.userInfoFailed') + ': ' + (err.message || err))
                    return
                  }
                  setQrStatus(t('ui.loginSuccess'))
                  await refreshUser()
                  setOpen(false)
                  reconnectAfterLogin()
                } else {
                  setQrStatus(t('ui.missingToken'))
                }
                return
              }
              if (codeCode === '0000' && boCode === '4002') {
                setQrStatus(t('ui.waitingScan'))
                return
              }
              if (codeCode === '0000' && boCode === '1002') {
                markQrExpired()
                return
              }
              stopQr()
              setQrExpired(false)
              setQrFailed(false)
              setQrStatus(result.bo?.msg || boCode || t('ui.loginFailed'))
            } catch {
              setQrStatus(t('ui.networkError'))
            }
          }, 2000)
        } catch (err) {
          markQrFailed(err.message || t('ui.qrGenerateFailed'))
        }
      }, [config.loginSystemCode, config.originSystemCode, markQrExpired, markQrFailed, refreshUser, stopQr])

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
          reconnectAfterLogin()
        } catch (err) {
          setFbErr(apiMessage(err) || t('ui.loginFailed'))
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
          const width = Math.min(300, window.innerWidth - 24)
          // Keep panel aligned to the badge (footer), not mid-sidebar.
          const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))
          const gap = 8
          const bottom = Math.max(8, window.innerHeight - rect.top + gap)
          setAnchor({ left, bottom, width })
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
        ? (user.userName || user.name || (t('ui.userPrefix') + user.empNo))
        : (loading ? '...' : t('ui.notLoggedIn'))
      const initials = String(displayName).slice(0, 2).toUpperCase()
      const label = roleLabel(user?.role)
      const perms = user?.permissions || {}
      const qrOverlay = qrExpired || qrFailed
      const qrOverlayTitle = qrExpired
        ? t('ui.qrExpired')
        : (qrStatus || t('ui.qrGenerateFailed'))
      const qrOverlayHint = t('ui.qrExpiredHint')

      return h('div', {
        ref: rootRef,
        className: 'uds-auth-host' + (wide ? '' : ' is-rail'),
        'data-uds-auth-host': 'sidebar-footer',
      },
      open && anchor && h('section', {
        className: 'uds-auth-panel',
        style: {
          left: anchor.left,
          bottom: anchor.bottom,
          top: 'auto',
          width: anchor.width,
        },
        'aria-label': 'UAC',
      },
      !user
        ? (loginMode === 'qr'
          ? h(React.Fragment, null,
            h('div', { className: 'uds-auth-info' },
              h('div', { className: 'uds-auth-info-name' }, qrOverlay ? qrOverlayTitle : t('ui.notLoggedIn')),
              h('div', { className: 'uds-auth-info-detail' }, qrOverlay ? qrOverlayHint : t('ui.pleaseScan')),
            ),
            h('div', { className: 'uds-auth-qr' },
              (qrImg || qrOverlay) && h('div', {
                className: 'uds-auth-qr-frame' + (qrOverlay ? ' is-expired' : ''),
              },
                qrImg ? h('img', { src: qrImg, alt: 'QR' }) : h('div', {
                  style: {
                    width: '100%',
                    height: '100%',
                    background: 'var(--dsw-alias-bg-module-platform, #f4f5f7)',
                  },
                }),
                qrOverlay && h('div', { className: 'uds-auth-qr-overlay' },
                  h('div', { className: 'uds-auth-qr-overlay-title' }, qrOverlayTitle),
                  h('div', { className: 'uds-auth-qr-overlay-hint' }, qrOverlayHint),
                  h('button', {
                    type: 'button',
                    className: 'uds-auth-qr-refresh',
                    'aria-label': t('ui.refreshQr'),
                    title: t('ui.refreshQr'),
                    onClick: startQr,
                  },
                    h('svg', {
                      width: 22,
                      height: 22,
                      viewBox: '0 0 24 24',
                      fill: 'none',
                      stroke: 'currentColor',
                      strokeWidth: 2.4,
                      strokeLinecap: 'round',
                      strokeLinejoin: 'round',
                      'aria-hidden': 'true',
                    },
                      h('path', { d: 'M21 12a9 9 0 1 1-2.6-6.2' }),
                      h('polyline', { points: '21 3 21 9 15 9' }),
                    ),
                  ),
                ),
              ),
              !qrOverlay && h('div', { className: 'uds-auth-qr-status' }, qrStatus || t('ui.loading')),
            ),
            fallbackEnabled && h('button', {
              type: 'button',
              className: 'uds-auth-btn-link',
              onClick: () => { stopQr(); setLoginMode('fallback'); setFbErr('') },
            }, t('ui.fallbackLink')),
          )
          : h(React.Fragment, null,
            h('div', { className: 'uds-auth-info' },
              h('div', { className: 'uds-auth-info-name' }, t('ui.fallbackLogin')),
              h('div', { className: 'uds-auth-info-detail' }, t('ui.fallbackDetail')),
            ),
            h('div', { className: 'uds-auth-fallback' },
              h('label', { htmlFor: 'uds-fb-user' }, t('ui.username')),
              h('input', {
                id: 'uds-fb-user',
                value: fbUser,
                onChange: (e) => setFbUser(e.target.value),
                autoComplete: 'username',
              }),
              h('label', { htmlFor: 'uds-fb-pass' }, t('ui.password')),
              h('input', {
                id: 'uds-fb-pass',
                type: 'password',
                value: fbPass,
                onChange: (e) => setFbPass(e.target.value),
                autoComplete: 'current-password',
                onKeyDown: (e) => { if (e.key === 'Enter') submitFallback() },
              }),
              fbErr && h('div', { className: 'uds-auth-settings-msg err' }, fbErr),
              h('button', {
                type: 'button',
                className: 'uds-auth-btn uds-auth-btn-primary',
                style: { width: '100%', margin: '12px 0 0' },
                disabled: fbBusy,
                onClick: submitFallback,
              }, fbBusy ? t('ui.loggingIn') : t('ui.login')),
            ),
            h('button', {
              type: 'button',
              className: 'uds-auth-btn-link',
              onClick: () => setLoginMode('qr'),
            }, t('ui.backToQr')),
          ))
        : h(React.Fragment, null,
          h('div', { className: 'uds-auth-info' },
            h('div', { className: 'uds-auth-info-name' }, displayName),
            h('div', { className: 'uds-auth-info-detail' }, h('span', { className: 'uds-auth-info-detail-label' }, t('ui.empNo')), user.empNo || '-'),
            h('div', { className: 'uds-auth-info-detail' }, h('span', { className: 'uds-auth-info-detail-label' }, t('ui.role')), label || user.role || '-'),
            user.department && h('div', { className: 'uds-auth-info-detail' }, h('span', { className: 'uds-auth-info-detail-label' }, t('ui.department')), user.department),
          ),
          h('button', {
            type: 'button', className: 'uds-auth-btn uds-auth-btn-danger',
            onClick: async () => {
              try { await fetchJson('/uds-auth/api/logout', { method: 'POST' }) } catch { /* ignore */ }
              clearAuthCookies()
              setUser(null)
              setOpen(false)
              document.documentElement.setAttribute('data-uds-logged-in', '0')
              document.documentElement.setAttribute('data-uds-can-settings', '0')
              document.documentElement.setAttribute('data-uds-can-create-ws', '0')
              clearSessionIfAnonymous(window.__udsAuthSessions)
              window.dispatchEvent(new Event('uds-auth-changed'))
              try { softReconnectAuth() } catch { /* ignore */ }
            },
          }, t('ui.logout')),
        ),
      ),
      h('button', {
        type: 'button',
        className: 'uds-auth-badge' + (user ? '' : ' uds-auth-badge-unauth'),
        'aria-expanded': open,
        'aria-label': displayName || 'UAC',
        title: displayName || 'UAC',
        onClick: () => setOpen((v) => !v),
      },
      h('span', { className: 'uds-auth-badge-label' }, displayName),
      ),
      )
    }

    function apply(ctx) {
      localeHost = ctx
      translate = makeTranslator(ctx)

      ctx.effect(() => {
        if (!ctx.locale || typeof ctx.locale.register !== 'function') return undefined
        try {
          return ctx.locale.register(LOCALE_NS, {
            zh: UDS_I18N_MESSAGES.zh,
            en: UDS_I18N_MESSAGES.en,
          })
        } catch {
          try {
            const offZh = ctx.locale.register(LOCALE_NS, 'zh', UDS_I18N_MESSAGES.zh)
            const offEn = ctx.locale.register(LOCALE_NS, 'en', UDS_I18N_MESSAGES.en)
            return () => { offZh && offZh(); offEn && offEn() }
          } catch {
            return undefined
          }
        }
      }, 'uds-auth: locale')

      try {
        ctx.inject(['connection'], (cctx) => {
          window.__udsAuthReconnect = () => {
            try { cctx.connection.reconnect() } catch { window.location.reload() }
          }
        })
      } catch { /* connection may be unavailable */ }


      // Default ACL attrs before /api/me — anonymous stays locked until AuthBadge confirms.
      ctx.effect(() => {
        const root = document.documentElement
        // Cookie alone is not enough; lock until /api/me sets real identity.
        if (!getEmpNo()) {
          root.setAttribute('data-uds-logged-in', '0')
        } else if (!root.getAttribute('data-uds-logged-in')) {
          // Optimistic cookie presence; AuthBadge will correct to 0/1.
          root.setAttribute('data-uds-logged-in', '0')
        }
        if (!root.getAttribute('data-uds-auth-ready')) {
          root.setAttribute('data-uds-auth-ready', '0')
        }
        if (!root.getAttribute('data-uds-can-create-ws')) {
          root.setAttribute('data-uds-can-create-ws', '0')
        }
        if (!root.getAttribute('data-uds-can-settings')) {
          root.setAttribute('data-uds-can-settings', '0')
        }
        return undefined
      }, 'uds-auth: bootstrap-acl-attrs')


      ctx.effect(() => {
        const tag = document.createElement('style')
        tag.id = 'uds-auth-client-css'
        tag.setAttribute('data-plugin', name)
        tag.textContent = CSS
        document.head.appendChild(tag)
        return () => tag.remove()
      }, 'uds-auth: styles')

      ctx.effect(() => {
        let settingsGateDispose = null
        const syncSettingsGate = async () => {
          let canSettings = false
          try {
            const me = await fetchJson('/uds-auth/api/me')
            canSettings = !!(me?.data?.permissions?.canAccessSettings)
          } catch { canSettings = false }
          if (canSettings) {
            if (settingsGateDispose) { try { settingsGateDispose() } catch {} settingsGateDispose = null }
            return
          }
          if (settingsGateDispose) return
          settingsGateDispose = ctx.slots.register({
            name: 'sidebar.settings',
            id: 'uds-auth-settings-gate',
            order: 9999,
          }, function UdsAuthSettingsGate() { return null })
        }
        syncSettingsGate()
        const mePoll = setInterval(syncSettingsGate, 15000)
        const onFocus = () => { syncSettingsGate() }
        window.addEventListener('focus', onFocus)
        return () => {
          clearInterval(mePoll)
          window.removeEventListener('focus', onFocus)
          if (settingsGateDispose) { try { settingsGateDispose() } catch {} }
        }
      }, 'uds-auth: settings-gate')


      // Defense in depth: never show Host session rows while UDS cookies are absent.
      // Covers ALS misses on /api and broadcast api-session/added leaks.
      // Use ctx.get (optional) — sandboxed clients cannot ctx.inject undeclared services.
      ctx.effect(() => {
        let onAuthChanged = null
        let installedRpc = false
        let installedSessions = false

        const install = () => {
          
        // Block anonymous calls to dsh-ops-cron (定时任务) HTTP API.
        if (!window.__udsAuthCronFetchGate) {
          window.__udsAuthCronFetchGate = true
          const origFetch = window.fetch.bind(window)
          window.fetch = async function udsAuthFetch(input, init) {
            const url = typeof input === 'string' ? input : (input && input.url) || ''
            if (!isLoggedInInUi() && String(url).includes('/dsh-ops-cron') && !String(url).includes('/dsh-ops-cron/health')) {
              return new Response(JSON.stringify({
                ok: false,
                error: 'login_required',
                message: t('ui.cronLoginRequired'),
              }), { status: 401, headers: { 'content-type': 'application/json' } })
            }
            return origFetch(input, init)
          }
        }

        const connection = ctx.get('connection')
          const rpc = connection && connection.rpc
          if (!installedRpc && rpc && typeof rpc.call === 'function' && !rpc.__udsAuthListGate) {
            installedRpc = true
            rpc.__udsAuthListGate = true
            const origCall = rpc.call.bind(rpc)
            rpc.call = async function udsAuthRpcCall(channel, endpoint, payload, signal) {
              const result = await origCall(channel, endpoint, payload, signal)
              if (!isLoggedInInUi()) {
              if (channel === '/api') {
                if (endpoint === 'session/list') return { ok: true, value: { items: [] } }
                if (endpoint === 'session/search') return { ok: true, value: { items: [], hasMore: false } }
              }
            }
            if (
              channel === '/api'
              && (
                endpoint === 'directoryPicker/pick'
                || endpoint === 'directoryPicker/list'
                || endpoint === 'directoryPicker/createDirectory'
              )
              && document.documentElement.getAttribute('data-uds-can-create-ws') !== '1'
            ) {
              return {
                ok: false,
                error: {
                  code: 'gateway/forbidden',
                  message: getEmpNo() ? t('ui.workspaceCreateForbidden') : t('ui.workspaceLoginRequired'),
                },
              }
            }
            return result
            }
          }

          const sessions = ctx.get('sessions')
          if (!installedSessions && sessions && !sessions.__udsAuthListGate) {
            installedSessions = true
            sessions.__udsAuthListGate = true
            const origAdded = sessions.handleSessionAdded && sessions.handleSessionAdded.bind(sessions)
            if (origAdded) {
              sessions.handleSessionAdded = (summary) => {
                if (!isLoggedInInUi()) return
                return origAdded(summary)
              }
            }
            const origActivity = sessions.handleSessionActivity && sessions.handleSessionActivity.bind(sessions)
            if (origActivity) {
              sessions.handleSessionActivity = (sessionId, updatedAt) => {
                if (!isLoggedInInUi()) return
                return origActivity(sessionId, updatedAt)
              }
            }
            const refresh = () => {
              if (typeof sessions.refresh === 'function') void sessions.refresh()
            }
            refresh()
            onAuthChanged = refresh
            window.addEventListener('uds-auth-changed', onAuthChanged)
          }
          return installedRpc && installedSessions
        }

        install()
        const timer = installedRpc && installedSessions ? null : setInterval(() => {
          if (install() && timer) clearInterval(timer)
        }, 300)

        return () => {
          if (timer) clearInterval(timer)
          if (onAuthChanged) window.removeEventListener('uds-auth-changed', onAuthChanged)
        }
      }, 'uds-auth: session-list-gate')
      ctx.effect(() => {
        let sessions = null
        let unsub = null
        const bind = () => {
          try { sessions = ctx.get('sessions') || sessions } catch { /* ignore */ }
          window.__udsAuthSessions = sessions
          if (unsub) { try { unsub() } catch { /* ignore */ } unsub = null }
          if (sessions && sessions.list && typeof sessions.list.subscribe === 'function') {
            unsub = sessions.list.subscribe(() => { clearSessionIfAnonymous(sessions) })
          }
          clearSessionIfAnonymous(sessions)
        }
        bind()
        const onAuth = () => { bind() }
        window.addEventListener('uds-auth-changed', onAuth)
        const mo = new MutationObserver(() => { clearSessionIfAnonymous(window.__udsAuthSessions) })
        mo.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ['data-uds-logged-in', 'data-uds-auth-ready'],
        })
        const timer = setInterval(bind, 500)
        setTimeout(() => clearInterval(timer), 20000)
        return () => {
          clearInterval(timer)
          mo.disconnect()
          window.removeEventListener('uds-auth-changed', onAuth)
          if (unsub) { try { unsub() } catch { /* ignore */ } }
        }
      }, 'uds-auth: clear-session-when-anonymous')




      ctx.effect(() => {
        let disposers = []
        const Gate = function UdsAuthDirectoryFlowGate(props) {
          React.useEffect(() => {
            if (props && props.open) {
              try { props.onCancel && props.onCancel() } catch { /* ignore */ }
            }
          }, [props && props.open])
          return null
        }
        const installGate = () => {
          if (disposers.length) return
          for (const slotName of [
            'sidebar.workspaces.directoryFlow',
            'conversation.hero.workspace.directoryFlow',
          ]) {
            try {
              disposers.push(ctx.slots.register({
                name: slotName,
                id: 'uds-auth-dir-gate',
                order: 9999,
              }, Gate))
            } catch { /* slot may be undeclared briefly */ }
          }
        }
        const clearGate = () => {
          for (const d of disposers) {
            try { d() } catch { /* ignore */ }
          }
          disposers = []
        }
        // Deny folder pick by default — no race with native directory picker.
        installGate()
        const sync = async () => {
          let canCreate = false
          try {
            const me = await fetchJson('/uds-auth/api/me')
            canCreate = !!(me && me.data && me.data.permissions && me.data.permissions.canCreateWorkspace)
          } catch { canCreate = false }
          if (canCreate) clearGate()
          else installGate()
        }
        sync()
        const timer = setInterval(sync, 15000)
        const onFocus = () => { sync() }
        const onAuth = () => { sync() }
        window.addEventListener('focus', onFocus)
        window.addEventListener('uds-auth-changed', onAuth)
        return () => {
          clearInterval(timer)
          window.removeEventListener('focus', onFocus)
          window.removeEventListener('uds-auth-changed', onAuth)
          clearGate()
        }
      }, 'uds-auth: directory-flow-gate')


      ctx.effect(() => {
        // Open/choose workspace is super_admin-only (canCreateWorkspace).
        // Everyone else uses the auto-provisioned per-user workspace and must not open the picker.
        const CHOOSER = hostAriaSel('chooseWorkspace')
        // Inert composer: onClick lives on the card (cardWorkspaceTrigger), not the labeled node.
        const TRIGGER_CARD = '[class*="cardWorkspaceTrigger"]'
        const SURFACE = CHOOSER + ', ' + TRIGGER_CARD
        const canOpenWorkspace = () => document.documentElement.getAttribute('data-uds-can-create-ws') === '1'
        const isChooser = (node) => {
          if (!node || !node.closest) return null
          return node.closest(SURFACE)
        }
        const unlockEl = (el) => {
          if (el.dataset.udsWsLocked !== '1') return
          el.style.display = ''
          el.style.pointerEvents = ''
          el.style.opacity = ''
          el.style.cursor = ''
          if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            el.removeAttribute('disabled')
          }
          el.removeAttribute('aria-disabled')
          el.removeAttribute('tabindex')
          delete el.dataset.udsWsLocked
        }
        const lockEl = (el, hide) => {
          el.dataset.udsWsLocked = '1'
          if (hide) el.style.display = 'none'
          el.style.pointerEvents = 'none'
          el.style.opacity = hide ? '' : '0.45'
          el.style.cursor = 'not-allowed'
          el.setAttribute('aria-disabled', 'true')
          el.setAttribute('tabindex', '-1')
          if (el.tagName === 'BUTTON' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            try { el.setAttribute('disabled', 'true') } catch { /* ignore */ }
          }
        }
        const freezeChoosers = () => {
          const loggedIn = document.documentElement.getAttribute('data-uds-logged-in') === '1'
          const canCreate = canOpenWorkspace()
          // Clear stale locks left on the composer card after it leaves trigger mode.
          document.querySelectorAll('[data-uds-ws-locked="1"]').forEach((el) => {
            const stillChooser = el.matches && (el.matches(CHOOSER) || el.matches(TRIGGER_CARD))
            if (canCreate || !stillChooser || (loggedIn && el.matches(TRIGGER_CARD))) unlockEl(el)
          })
          if (canCreate) {
            document.querySelectorAll(SURFACE).forEach(unlockEl)
            return
          }
          // Non-creators: hide labeled chooser chips only.
          document.querySelectorAll(CHOOSER).forEach((el) => lockEl(el, true))
          // Lock inert trigger card only while anonymous; logged-in users
          // auto-bind a personal workspace and must not keep pointer-events:none.
          if (!loggedIn) {
            document.querySelectorAll(TRIGGER_CARD).forEach((el) => lockEl(el, false))
          }
        }

        const block = (event) => {
          if (canOpenWorkspace()) return
          const hit = isChooser(event.target)
          if (!hit) return
          const loggedIn = document.documentElement.getAttribute('data-uds-logged-in') === '1'
          // Logged-in non-creators: still block labeled "选择工作区" / trigger clicks
          // that open the picker; do not leave the card permanently disabled.
          if (loggedIn && hit.matches && hit.matches(TRIGGER_CARD) && !hit.matches(CHOOSER)) {
            event.preventDefault()
            event.stopPropagation()
            if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation()
            return
          }
          event.preventDefault()
          event.stopPropagation()
          if (typeof event.stopImmediatePropagation === 'function') event.stopImmediatePropagation()
        }
        document.addEventListener('click', block, true)
        document.addEventListener('pointerdown', block, true)
        document.addEventListener('mousedown', block, true)
        document.addEventListener('keydown', (event) => {
          if (canOpenWorkspace()) return
          if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') return
          if (!isChooser(event.target)) return
          event.preventDefault()
          event.stopPropagation()
        }, true)

        let workspaceDispose = null
        const LockedWorkspace = function UdsAuthLockedWorkspace(props) {
          React.useEffect(() => {
            if (props && props.open) {
              try { props.onClose && props.onClose() } catch { /* ignore */ }
            }
          }, [props && props.open])
          return null
        }
        const installWorkspaceLock = () => {
          if (workspaceDispose) return
          try {
            workspaceDispose = ctx.slots.register({
              name: 'conversation.hero.workspace',
              id: 'uds-auth-workspace-lock',
              order: 9999,
            }, LockedWorkspace)
          } catch { /* slot may be undeclared briefly */ }
        }
        const clearWorkspaceLock = () => {
          if (workspaceDispose) {
            try { workspaceDispose() } catch { /* ignore */ }
            workspaceDispose = null
          }
        }
        // Deny open-workspace by default until /api/me proves canCreateWorkspace.
        if (!canOpenWorkspace()) installWorkspaceLock()
        freezeChoosers()

        const syncWorkspaceSlot = async () => {
          let canCreate = document.documentElement.getAttribute('data-uds-can-create-ws') === '1'
          try {
            const me = await fetchJson('/uds-auth/api/me')
            const user = me && me.authenticated && me.data ? me.data : null
            const perms = user && user.permissions ? user.permissions : {}
            canCreate = !!perms.canCreateWorkspace
            document.documentElement.setAttribute('data-uds-logged-in', user ? '1' : '0')
            document.documentElement.setAttribute('data-uds-can-create-ws', canCreate ? '1' : '0')
            document.documentElement.setAttribute(
              'data-uds-can-settings',
              user && perms.canAccessSettings ? '1' : '0',
            )
          } catch {
            if (!getEmpNo()) {
              canCreate = false
              document.documentElement.setAttribute('data-uds-logged-in', '0')
              document.documentElement.setAttribute('data-uds-can-create-ws', '0')
            }
          }
          if (canCreate) clearWorkspaceLock()
          else installWorkspaceLock()
          freezeChoosers()
        }
        syncWorkspaceSlot()
        const timer = setInterval(syncWorkspaceSlot, 10000)
        const onAuth = () => { syncWorkspaceSlot() }
        window.addEventListener('uds-auth-changed', onAuth)
        window.addEventListener('focus', onAuth)
        const mo = new MutationObserver(() => { freezeChoosers() })
        mo.observe(document.documentElement, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ['data-uds-can-create-ws', 'data-uds-logged-in', 'aria-label', 'class'],
        })

        return () => {
          clearInterval(timer)
          mo.disconnect()
          document.removeEventListener('click', block, true)
          document.removeEventListener('pointerdown', block, true)
          document.removeEventListener('mousedown', block, true)
          window.removeEventListener('uds-auth-changed', onAuth)
          window.removeEventListener('focus', onAuth)
          clearWorkspaceLock()
        }
      }, 'uds-auth: workspace-click-lock')
      ctx.effect(() => {
        let busy = false
        let tries = 0
        const bindPersonalWorkspace = async () => {
          if (busy) return
          if (document.documentElement.getAttribute('data-uds-logged-in') !== '1') return
          if (document.documentElement.getAttribute('data-uds-auth-ready') !== '1') return
          // Super/fallback keep full workspace browser — do not force personal workspace.
          if (document.documentElement.getAttribute('data-uds-can-create-ws') === '1') return
          if (document.documentElement.getAttribute('data-uds-can-create-ws') !== '0') return
          let sessions = null
          try { sessions = ctx.get('sessions') } catch { sessions = null }
          if (!sessions || typeof sessions.create !== 'function') return
          try {
            const snap = sessions.list && sessions.list.getSnapshot && sessions.list.getSnapshot()
            if (snap && snap.current != null) return
          } catch { /* ignore */ }
          busy = true
          try {
            const me = await fetchJson('/uds-auth/api/me')
            const wsId = me && me.data && me.data.workspaceId
            if (!me?.authenticated || !wsId) return
            const sessionId = await sessions.create({ workspaceId: wsId })
            if (sessionId && typeof sessions.open === 'function') sessions.open(sessionId)
          } catch (err) {
            console.warn('[uds-auth] auto-bind personal workspace failed:', err && err.message ? err.message : err)
          } finally {
            busy = false
          }
        }
        const tick = () => {
          if (tries++ > 40) return
          void bindPersonalWorkspace()
        }
        tick()
        window.addEventListener('uds-auth-changed', tick)
        const timer = setInterval(tick, 1500)
        setTimeout(() => clearInterval(timer), 60000)
        return () => {
          clearInterval(timer)
          window.removeEventListener('uds-auth-changed', tick)
        }
      }, 'uds-auth: auto-bind-personal-workspace')
      ctx.effect(() => {
        const sync = () => {
          const root = document.documentElement
          if (root.getAttribute('data-uds-auth-ready') !== '1') return
          if (root.getAttribute('data-uds-logged-in') !== '1') {
            try { window.sessionStorage.removeItem('uds-auth-flat-reloaded') } catch { /* ignore */ }
            try { window.sessionStorage.removeItem('uds-auth-ws-reloaded') } catch { /* ignore */ }
            return
          }
          // Super/fallback: restore workspace partitions (undo forced flat).
          if (root.getAttribute('data-uds-can-create-ws') === '1') {
            const restored = ensureWorkspaceGroupedSidebar()
            if (restored && !window.sessionStorage.getItem('uds-auth-ws-reloaded')) {
              try {
                window.sessionStorage.setItem('uds-auth-ws-reloaded', '1')
                window.location.reload()
              } catch { /* ignore */ }
            }
            try { window.sessionStorage.removeItem('uds-auth-flat-reloaded') } catch { /* ignore */ }
            return
          }
          if (root.getAttribute('data-uds-can-create-ws') !== '0') return
          const switched = ensureFlatSessionSidebar()
          expandHiddenWorkspaceGroups()
          if (switched && !window.sessionStorage.getItem('uds-auth-flat-reloaded')) {
            try {
              window.sessionStorage.setItem('uds-auth-flat-reloaded', '1')
              window.location.reload()
            } catch { /* ignore */ }
          }
        }
        sync()
        const onAuth = () => { sync() }
        window.addEventListener('uds-auth-changed', onAuth)
        const moAttrs = new MutationObserver(() => { sync() })
        moAttrs.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ['data-uds-logged-in', 'data-uds-can-create-ws', 'data-uds-auth-ready'],
        })
        const mo = new MutationObserver(() => { expandHiddenWorkspaceGroups() })
        mo.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-expanded', 'class'] })
        const timer = setInterval(expandHiddenWorkspaceGroups, 2000)
        setTimeout(() => clearInterval(timer), 30000)
        return () => {
          clearInterval(timer)
          mo.disconnect()
          moAttrs.disconnect()
          window.removeEventListener('uds-auth-changed', onAuth)
        }
      }, 'uds-auth: session-only-sidebar')





      // sidebar.footer.action; layout effect lays footArea as one row: Settings | UAC login
      ctx.slots.inject('sidebar.footer.action', () => ctx.slots.register({
        name: 'sidebar.footer.action',
        id: 'uds-auth-login',
        order: 100,
        label: 'UAC',
      }, AuthBadge))

      ctx.slots.inject('settings.section', () => ctx.slots.register({
        name: 'settings.section',
        id: 'uds-auth',
        order: 22,
        label: () => t('ui.settingsTitle'),
        locale: LOCALE_NS,
        icon: 'users',
      }, AuthSettingsSection))
    }

    exports.name = name
    exports.inject = inject
    exports.apply = apply
    return module.exports
  },
})
