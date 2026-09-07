/**
 * uds-auth 配置工具
 * Config schema 定义在 lib/index.js（由 DSH host 提供 @deepseek-ai/schemastery）
 * 这里只做纯 JS 的默认值和工具函数，不依赖 host 运行时
 *
 * 可配置字段（部署相关，在 DSH 设置面板可改）：
 *   uacBaseUrl      UAC 基础 URL
 *   userSearchUrl   icenterapi 用户搜索接口
 *   loginSystemCode 业务系统 Code
 *   originSystemCode 来源系统 Code
 *
 * 内部常量（UDS 固定协议，不暴露给用户）：
 *   uacQrVerifyPath, cookie 名称, header 名称, session 等
 */

const UDS_AUTH_SETTINGS_NAMESPACE = 'uds-auth'

// 可配置字段的默认值（与 lib/index.js 里 Config schema 保持一致）
const DEFAULT_CONFIG = {
  uacBaseUrl: 'https://uac.zte.com.cn',
  userSearchUrl: 'https://icenterapi.zte.com.cn/zte-km-icenter-addresearch/user/plain/docs/search',
  loginSystemCode: '100000455558',
  originSystemCode: '',
}

// 内部常量（不暴露）
const INTERNAL = {
  uacQrVerifyPath: '/uacqr/auth/qrcode/verify.serv',
  cookieEmpNo: 'PORTALSSOUser',
  cookieAuthValue: 'PORTALSSOCookie',
  altCookieEmpNo: 'ZTEDPGSSOUser',
  altCookieAuthValue: 'ZTEDPGSSOCookie',
  empNoHeader: 'X-Emp-No',
  authValueHeader: 'X-Auth-Value',
  session: {
    storeType: 'memory',
    redisUrl: 'redis://localhost:6379',
    cookieName: 'UDS_SESSION',
    cookieMaxAge: 1800000,
  },
}

export { DEFAULT_CONFIG, INTERNAL, UDS_AUTH_SETTINGS_NAMESPACE }

export function loadConfig(custom = {}) {
  return { ...DEFAULT_CONFIG, ...(custom || {}) }
}

export function buildVerifyUrl(uacBaseUrl, uacQrVerifyPath) {
  if (/^https?:\/\//.test(uacQrVerifyPath)) return uacQrVerifyPath
  return (uacBaseUrl.replace(/\/$/, '') + '/' + uacQrVerifyPath.replace(/^\//, ''))
}

export function validateConfig(config) {
  if (!config?.uacBaseUrl) throw new Error('uacBaseUrl is required')
  return true
}
