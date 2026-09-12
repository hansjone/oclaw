/**
 * uds-auth i18n — single source for UI + API user-facing strings.
 * Locales: zh (default), en. Keys are stable error/UI ids.
 *
 * Browser client.js embeds a copy of MESSAGES (ModuleLoader cannot import this file).
 * When changing strings here, also refresh the `UDS_I18N_MESSAGES` block in lib/client.js
 * (search for `uds-auth-i18n-begin`).
 */

export const DEFAULT_LOCALE = 'zh'

/** @type {Record<string, Record<string, string>>} */
export const MESSAGES = {
  zh: {
    // roles
    'role.super_admin': '超级管理员',
    'role.admin': '管理员',
    'role.user': '普通用户',
    'role.fallback_admin': '应急管理员',
    'role.badge.super_admin': '超管',
    'role.badge.admin': '管理员',
    'role.badge.fallback_admin': '应急',
    'role.badge.user': '',

    // settings / users
    'ui.settingsTitle': 'UAC 认证',
    'ui.settingsIntro': '工号+token 双校验；UAC 挂死时用应急账号 administrator 密码登录。',
    'ui.loginRequiredPage': '请先登录后查看此页',
    'ui.roleHint': '当前角色：{role}。首位扫码登录且 roles.json 为空时会自动成为超管；普通 admin 需超管在「用户管理」提权后再扫码登录。应急账号 administrator 需超管先设密码，再在登录面板用账密登录。',
    'ui.deployConfig': '部署配置',
    'ui.userSearchUrl': '用户搜索 URL（token 校验）',
    'ui.workspaceRoot': '工作区根目录（空=$DSH_HOME/user-workspaces）',
    'ui.saveConfig': '保存配置',
    'ui.saving': '保存中...',
    'ui.configSaved': '配置已保存',
    'ui.saveFailed': '保存失败',
    'ui.fallbackTitle': '应急登录（UAC 不可用）',
    'ui.fallbackStatus': '状态：{status}。可在此改密或关闭。仅在扫码不可用时从登录面板切换。',
    'ui.enabled': '已启用',
    'ui.disabled': '未启用',
    'ui.fallbackPassword': '应急密码（至少 6 位）',
    'ui.saveFallbackPassword': '保存应急密码',
    'ui.fallbackPasswordSet': '应急密码已设置',
    'ui.confirmClearFallback': '确认清除应急密码？',
    'ui.clear': '清除',
    'ui.userManagement': '用户管理',
    'ui.searchEmpNo': '搜索工号',
    'ui.search': '搜索',
    'ui.loading': '加载中...',
    'ui.loadFailed': '加载失败',
    'ui.empNo': '工号',
    'ui.role': '角色',
    'ui.actions': '操作',
    'ui.noUsers': '暂无用户',
    'ui.delete': '删除',
    'ui.confirmDelete': '确认删除 {empNo}？',
    'ui.pager': '共 {total} 人，第 {page} / {totalPages} 页',
    'ui.prevPage': '上一页',
    'ui.nextPage': '下一页',
    'ui.add': '添加',
    'ui.department': '部门',

    // login panel
    'ui.notLoggedIn': '未登录',
    'ui.pleaseScan': '请使用 iCenter 扫码登录',
    'ui.refreshQr': '刷新二维码',
    'ui.fallbackLink': 'UAC 不可用？应急账号登录',
    'ui.fallbackLogin': '应急登录',
    'ui.fallbackDetail': 'UAC / 扫码不可用时使用',
    'ui.localKeyLink': '本机密钥解锁',
    'ui.localKeyLogin': '本机密钥解锁',
    'ui.localKeyDetail': '用密封盒口令解密后登录（仅设环境变量不会自动登录）',
    'ui.localKey': '解密密钥',
    'ui.username': '用户名',
    'ui.password': '密码',
    'ui.login': '登录',
    'ui.loggingIn': '登录中...',
    'ui.backToQr': '返回扫码登录',
    'ui.logout': '退出登录',
    'ui.userPrefix': '用户',

    // QR status
    'ui.qrGenerating': '正在生成二维码...',
    'ui.qrScanPrompt': '请使用 iCenter 扫码登录...',
    'ui.userInfoFailed': '用户信息查询失败',
    'ui.loginSuccess': '登录成功！',
    'ui.missingToken': '缺少 token，无法完成校验',
    'ui.waitingScan': '等待扫码...',
    'ui.qrExpired': '二维码已失效',
    'ui.qrExpiredHint': '请刷新后重新扫描',
    'ui.loginFailed': '登录失败',
    'ui.networkError': '网络错误...',
    'ui.qrGenerateFailed': '生成二维码失败',

    // client gates
    'ui.cronLoginRequired': '登录后才能使用定时任务',
    'ui.workspaceCreateForbidden': '只有超级管理员可以创建工作区',
    'ui.workspaceLoginRequired': '登录后才能使用工作区',

    // API / ACL errors (stable codes)
    'err.not_logged_in': '未登录',
    'err.forbidden_settings': '当前账号无设置权限',
    'err.forbidden_manage_users': '只有超级管理员可以管理用户',
    'err.forbidden_list_users': '只有超级管理员可以查看用户列表',
    'err.forbidden_set_role': '只有超级管理员可以修改角色',
    'err.forbidden_add_user': '只有超级管理员可以添加用户',
    'err.forbidden_remove_user': '只有超级管理员可以删除用户',
    'err.forbidden_set_fallback': '只有超级管理员可以设置应急密码',
    'err.forbidden_clear_fallback': '只有超级管理员可以清除应急密码',
    'err.invalid_role_params': '参数错误: empNo 和 role 必填',
    'err.emp_no_required': 'empNo 必填',
    'err.username_password_required': '用户名和密码必填',
    'err.invalid_credentials': '用户名或密码错误',
    'err.last_super_admin_demote': '系统至少需要 1 个超级管理员，不能降级最后一个',
    'err.last_super_admin_delete': '系统至少需要 1 个超级管理员，不能删除最后一个',
    'err.password_too_short': '密码至少 6 位',
    'err.config_not_ready': '配置未初始化',
    'err.request_failed': '请求失败',
    'err.method_not_allowed': '方法不允许',
    'err.missing_qr_params': '缺少 qrCodeKey 或 qrCodeValue',
    'err.missing_emp_token': '缺少 empNo 或 token',
    'err.user_search_failed': '用户搜索失败',
    'err.not_found': '未找到',
    'err.internal': '内部错误',
    'err.login_required_cron': '登录后才能使用定时任务',
    'err.login_required_session': '登录后才能访问会话',
    'err.login_required_create_session': '登录后才能创建会话',
    'err.login_required_workspace': '登录后才能使用工作区',
    'err.session_forbidden': '无权访问该会话',
    'err.session_workspace_only': '只能在自己的工作区创建会话',
    'err.workspace_path_only': '只能打开自己的工作区路径',
    'err.workspace_create_forbidden': '只有超级管理员可以创建工作区',
    'err.no_skill_credentials': '请先完成 UAC 扫码登录',
    'err.loopback_only_credentials': 'agent-credentials 仅允许本机访问',
    'err.loopback_only_outbound': 'outbound 仅允许本机访问',
    'err.url_required': '缺少 url',
    'err.invalid_url': '无效 url',
    'err.unsupported_protocol': '不支持的协议',
    'err.host_not_allowed': '主机不在白名单',
    'err.upstream_failed': '上游请求失败',
    'err.skill_credentials_not_ready': 'skill 凭证未就绪',
    'err.outbound_not_ready': 'outbound 未就绪',
    'err.local_admin_not_configured': '未配置本机管理员密封盒',
    'err.key_required': '请输入解密密钥',
    'err.decrypt_failed': '密钥无法解密，登录失败',
    'err.rate_limited': '尝试过多，请稍后再试',

    // API success
    'ok.logged_out': '已退出登录',
    'ok.config_saved': '配置已保存',
    'ok.role_updated': '{empNo} 角色已更新为 {role}',
    'ok.user_added': '{empNo} 已添加为 {role}',
    'ok.user_removed': '{empNo} 已删除',
    'ok.fallback_password_set': '应急管理员密码已设置',
    'ok.fallback_password_cleared': '应急管理员密码已清除',
    'ok.fallback_login': '应急管理员登录成功',
    'ok.local_admin_unlock': '本机密钥解锁成功',
  },
  en: {
    'role.super_admin': 'Super admin',
    'role.admin': 'Admin',
    'role.user': 'User',
    'role.fallback_admin': 'Emergency admin',
    'role.badge.super_admin': 'Super',
    'role.badge.admin': 'Admin',
    'role.badge.fallback_admin': 'Emergency',
    'role.badge.user': '',

    'ui.settingsTitle': 'UAC Auth',
    'ui.settingsIntro': 'EmpNo + token verification; when UAC is down, sign in with emergency account administrator.',
    'ui.loginRequiredPage': 'Sign in to view this page',
    'ui.roleHint': 'Current role: {role}. The first QR login with an empty roles.json becomes super admin; grant admin in User management then re-scan. Set the emergency password before using administrator on the login panel.',
    'ui.deployConfig': 'Deploy config',
    'ui.userSearchUrl': 'User search URL (token verify)',
    'ui.workspaceRoot': 'Workspace root (empty=$DSH_HOME/user-workspaces)',
    'ui.saveConfig': 'Save config',
    'ui.saving': 'Saving...',
    'ui.configSaved': 'Config saved',
    'ui.saveFailed': 'Save failed',
    'ui.fallbackTitle': 'Emergency login (UAC unavailable)',
    'ui.fallbackStatus': 'Status: {status}. Change or disable here. Switch from the login panel only when QR is unavailable.',
    'ui.enabled': 'Enabled',
    'ui.disabled': 'Disabled',
    'ui.fallbackPassword': 'Emergency password (min 6 chars)',
    'ui.saveFallbackPassword': 'Save emergency password',
    'ui.fallbackPasswordSet': 'Emergency password set',
    'ui.confirmClearFallback': 'Clear emergency password?',
    'ui.clear': 'Clear',
    'ui.userManagement': 'User management',
    'ui.searchEmpNo': 'Search empNo',
    'ui.search': 'Search',
    'ui.loading': 'Loading...',
    'ui.loadFailed': 'Load failed',
    'ui.empNo': 'EmpNo',
    'ui.role': 'Role',
    'ui.actions': 'Actions',
    'ui.noUsers': 'No users',
    'ui.delete': 'Delete',
    'ui.confirmDelete': 'Delete {empNo}?',
    'ui.pager': '{total} users, page {page} / {totalPages}',
    'ui.prevPage': 'Previous',
    'ui.nextPage': 'Next',
    'ui.add': 'Add',
    'ui.department': 'Department',

    'ui.notLoggedIn': 'Not signed in',
    'ui.pleaseScan': 'Scan with iCenter to sign in',
    'ui.refreshQr': 'Refresh QR',
    'ui.fallbackLink': 'UAC down? Emergency account',
    'ui.fallbackLogin': 'Emergency login',
    'ui.fallbackDetail': 'Use when UAC / QR is unavailable',
    'ui.localKeyLink': 'Unlock with local key',
    'ui.localKeyLogin': 'Local key unlock',
    'ui.localKeyDetail': 'Decrypt the sealed box with your passphrase (env alone does nothing)',
    'ui.localKey': 'Decryption key',
    'ui.username': 'Username',
    'ui.password': 'Password',
    'ui.login': 'Sign in',
    'ui.loggingIn': 'Signing in...',
    'ui.backToQr': 'Back to QR login',
    'ui.logout': 'Sign out',
    'ui.userPrefix': 'User',

    'ui.qrGenerating': 'Generating QR...',
    'ui.qrScanPrompt': 'Scan with iCenter to sign in...',
    'ui.userInfoFailed': 'User info lookup failed',
    'ui.loginSuccess': 'Signed in!',
    'ui.missingToken': 'Missing token; cannot verify',
    'ui.waitingScan': 'Waiting for scan...',
    'ui.qrExpired': 'QR code expired',
    'ui.qrExpiredHint': 'Refresh and scan again',
    'ui.loginFailed': 'Sign-in failed',
    'ui.networkError': 'Network error...',
    'ui.qrGenerateFailed': 'Failed to generate QR',

    'ui.cronLoginRequired': 'Sign in to use scheduled tasks',
    'ui.workspaceCreateForbidden': 'Only super admins can create workspaces',
    'ui.workspaceLoginRequired': 'Sign in to use workspaces',

    'err.not_logged_in': 'Not signed in',
    'err.forbidden_settings': 'No settings permission',
    'err.forbidden_manage_users': 'Only super admins can manage users',
    'err.forbidden_list_users': 'Only super admins can list users',
    'err.forbidden_set_role': 'Only super admins can change roles',
    'err.forbidden_add_user': 'Only super admins can add users',
    'err.forbidden_remove_user': 'Only super admins can remove users',
    'err.forbidden_set_fallback': 'Only super admins can set the emergency password',
    'err.forbidden_clear_fallback': 'Only super admins can clear the emergency password',
    'err.invalid_role_params': 'Invalid params: empNo and role required',
    'err.emp_no_required': 'empNo required',
    'err.username_password_required': 'Username and password required',
    'err.invalid_credentials': 'Invalid username or password',
    'err.last_super_admin_demote': 'At least one super admin is required; cannot demote the last one',
    'err.last_super_admin_delete': 'At least one super admin is required; cannot delete the last one',
    'err.password_too_short': 'Password must be at least 6 characters',
    'err.config_not_ready': 'Config not initialized',
    'err.request_failed': 'Request failed',
    'err.method_not_allowed': 'Method not allowed',
    'err.missing_qr_params': 'Missing qrCodeKey or qrCodeValue',
    'err.missing_emp_token': 'Missing empNo or token',
    'err.user_search_failed': 'User search failed',
    'err.not_found': 'Not found',
    'err.internal': 'Internal error',
    'err.login_required_cron': 'Sign in to use scheduled tasks',
    'err.login_required_session': 'Sign in to access sessions',
    'err.login_required_create_session': 'Sign in to create a session',
    'err.login_required_workspace': 'Sign in to use workspaces',
    'err.session_forbidden': 'No access to this session',
    'err.session_workspace_only': 'Sessions can only be created in your own workspace',
    'err.workspace_path_only': 'You can only open your own workspace path',
    'err.workspace_create_forbidden': 'Only super admins can create workspaces',
    'err.no_skill_credentials': 'Complete UAC QR sign-in first',
    'err.loopback_only_credentials': 'agent-credentials is loopback-only',
    'err.loopback_only_outbound': 'outbound is loopback-only',
    'err.url_required': 'url required',
    'err.invalid_url': 'invalid url',
    'err.unsupported_protocol': 'unsupported protocol',
    'err.host_not_allowed': 'host not allowed',
    'err.upstream_failed': 'upstream failed',
    'err.skill_credentials_not_ready': 'skill credentials not ready',
    'err.outbound_not_ready': 'outbound not ready',
    'err.local_admin_not_configured': 'Local admin sealed box is not configured',
    'err.key_required': 'Decryption key required',
    'err.decrypt_failed': 'Key could not decrypt — sign-in failed',
    'err.rate_limited': 'Too many attempts, try later',

    'ok.logged_out': 'Signed out',
    'ok.config_saved': 'Config saved',
    'ok.role_updated': '{empNo} role updated to {role}',
    'ok.user_added': '{empNo} added as {role}',
    'ok.user_removed': '{empNo} removed',
    'ok.fallback_password_set': 'Emergency admin password set',
    'ok.fallback_password_cleared': 'Emergency admin password cleared',
    'ok.fallback_login': 'Emergency admin signed in',
    'ok.local_admin_unlock': 'Local admin unlocked',
  },
}

/**
 * @param {unknown} lang
 * @returns {'zh' | 'en'}
 */
export function normalizeLocale(lang) {
  const raw = String(lang || '').trim().toLowerCase()
  if (!raw) return DEFAULT_LOCALE
  if (raw.startsWith('en')) return 'en'
  if (raw.startsWith('zh')) return DEFAULT_LOCALE
  return DEFAULT_LOCALE
}

/**
 * @param {string} key
 * @param {'zh' | 'en' | string} [locale]
 * @param {Record<string, string | number>} [vars]
 */
export function t(key, locale = DEFAULT_LOCALE, vars = {}) {
  const loc = normalizeLocale(locale)
  const table = MESSAGES[loc] || MESSAGES[DEFAULT_LOCALE]
  let text = table[key] || MESSAGES[DEFAULT_LOCALE][key] || key
  for (const [k, v] of Object.entries(vars || {})) {
    text = text.split('{' + k + '}').join(String(v))
  }
  return text
}

/** Role display label (full). */
export function roleLabel(role, locale = DEFAULT_LOCALE) {
  return t('role.' + String(role || 'user'), locale)
}

/** Compact badge label. */
export function roleBadge(role, locale = DEFAULT_LOCALE) {
  return t('role.badge.' + String(role || 'user'), locale)
}

/** Default zh labels for roles.json search / list (server-side). */
export const ROLE_LABELS_ZH = {
  super_admin: MESSAGES.zh['role.super_admin'],
  admin: MESSAGES.zh['role.admin'],
  user: MESSAGES.zh['role.user'],
  fallback_admin: MESSAGES.zh['role.fallback_admin'],
}

function parseCookie(header, name) {
  if (!header) return null
  const prefix = name + '='
  for (const part of String(header).split(';')) {
    const v = part.trim()
    if (v.startsWith(prefix)) {
      try { return decodeURIComponent(v.slice(prefix.length)) } catch { return v.slice(prefix.length) }
    }
  }
  return null
}

/**
 * Resolve locale from HTTP request + optional userContext.lang.
 * @param {import('node:http').IncomingMessage | null | undefined} req
 * @param {{ lang?: string } | null | undefined} [userContext]
 */
export function resolveLocale(req, userContext) {
  const headers = req?.headers || {}
  const cookie = headers.cookie || ''
  const fromCtx = userContext?.lang
  const fromHeader = headers['x-lang-id'] || headers['X-Lang-Id']
  const fromCookie = parseCookie(cookie, 'PORTALSSOLanguage')
    || parseCookie(cookie, 'ZTEDPGSSOLanguage')
  const accept = String(headers['accept-language'] || '').split(',')[0]
  return normalizeLocale(fromCtx || fromHeader || fromCookie || accept || DEFAULT_LOCALE)
}

/**
 * API error payload: stable `error` code + localized `message`.
 * @param {string} code
 * @param {'zh' | 'en' | string} locale
 * @param {Record<string, string | number>} [vars]
 */
export function apiError(code, locale, vars) {
  const key = code.startsWith('err.') || code.startsWith('ok.') ? code : 'err.' + code
  return {
    error: code.startsWith('err.') ? code.slice(4) : code,
    message: t(key, locale, vars),
  }
}

/**
 * @param {string} code
 * @param {'zh' | 'en' | string} locale
 * @param {Record<string, string | number>} [vars]
 */
export function apiOk(code, locale, vars) {
  const key = code.startsWith('ok.') ? code : 'ok.' + code
  return {
    message: t(key, locale, vars),
  }
}

/** Host UI aria-labels (zh + en) for CSS / DOM gates — not translated UI of this plugin. */
export const HOST_ARIA = {
  addWorkspace: ['添加工作区', 'Add workspace'],
  chooseWorkspace: ['选择工作区', 'Choose workspace'],
  sessions: ['会话', 'Sessions'],
}

export function ariaSelector(labels) {
  return labels.map((l) => '[aria-label="' + l + '"]').join(',')
}

export function buttonAriaSelector(labels) {
  return labels.map((l) => 'button[aria-label="' + l + '"]').join(',')
}
