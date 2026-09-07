/**
 * UDS Credential Validator with enhanced user info support
 * 
 * Mode 1 (verify): Call UDS verification API to validate token
 * Mode 2 (trust): Trust the credentials from request headers directly (for internal network)
 */

export class UdsValidator {
  /**
   * @param {object} config - Validator configuration
   */
  constructor(config = {}) {
    this.empNoHeader = (config.empNoHeader || 'X-Emp-No').toLowerCase()
    this.authValueHeader = (config.authValueHeader || 'X-Auth-Value').toLowerCase()
    this.langIdHeader = (config.langIdHeader || 'X-Lang-Id').toLowerCase()
    this.authMode = config.authMode || 'token+profile'
    this.hrApiUrl = config.hrApiUrl || 'https://icosg.dt.zte.com.cn/ihol/usercenter/pginfo/usercenter/plain/queryPersonGeneralInfo'
  }

  /**
   * 从 Cookie 头中解析单个 cookie 值
   */
  static parseCookie(cookieHeader, name) {
    if (!cookieHeader || typeof cookieHeader !== 'string') return null
    const pairs = cookieHeader.split(';')
    for (const pair of pairs) {
      const idx = pair.indexOf('=')
      if (idx < 0) continue
      const k = pair.slice(0, idx).trim()
      if (k === name) {
        return decodeURIComponent(pair.slice(idx + 1).trim())
      }
    }
    return null
  }

  /**
   * Extract UDS credentials from HTTP request headers.
   * 同时支持 cookie（QR 登录流程只设 cookie 不设 header）。
   * 优先级: header > cookie
   */
  extractCredentials(request) {
    const headers = request.headers || {}
    
    const getHeader = (name) => {
      if (headers[name] !== undefined) return headers[name]
      const lowerName = name.toLowerCase()
      if (headers[lowerName] !== undefined) return headers[lowerName]
      for (const key of Object.keys(headers)) {
        if (key.toLowerCase() === lowerName) return headers[key]
      }
      return undefined
    }

    const cookieHeader = headers.cookie || ''
    const empNo = getHeader(this.empNoHeader)
      || UdsValidator.parseCookie(cookieHeader, 'PORTALSSOUser')
      || UdsValidator.parseCookie(cookieHeader, 'ZTEDPGSSOUser')
    const token = getHeader(this.authValueHeader)
      || UdsValidator.parseCookie(cookieHeader, 'PORTALSSOCookie')
      || UdsValidator.parseCookie(cookieHeader, 'ZTEDPGSSOCookie')
    const lang = getHeader(this.langIdHeader)
      || UdsValidator.parseCookie(cookieHeader, 'PORTALSSOLanguage')
      || UdsValidator.parseCookie(cookieHeader, 'ZTEDPGSSOLanguage')
      || 'zh-CN'
    
    if (!empNo || !token) {
      return null
    }
    
    return {
      empNo: String(empNo).trim(),
      token: String(token).trim(),
      lang: String(lang).trim(),
    }
  }

  /**
   * Validate extracted credentials
   */
  validateCredentials(credentials) {
    if (!credentials) return false
    if (!credentials.empNo || typeof credentials.empNo !== 'string') return false
    if (!credentials.token || typeof credentials.token !== 'string') return false
    
    // Basic format validation
    if (credentials.empNo.length < 5) return false
    if (credentials.token.length < 10) return false
    
    return true
  }

  /**
   * Call HR API to get employee details
   */
  async fetchEmployeeInfo(empNo) {
    try {
      const response = await fetch(this.hrApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bo: {
            rows: [{ employeeNO: empNo }],
            pageNum: 1,
            pageSize: 1,
          }
        })
      })
      
      if (!response.ok) {
        return null
      }
      
      const data = await response.json()
      const rows = data?.bo?.rows
      
      if (rows && rows.length > 0) {
        const emp = rows[0]
        return {
          userId: emp.employeeNO || emp.empUIID || empNo,
          username: emp.empName || empNo,
          displayName: emp.empName || empNo,
          department: emp.orgNamePath || emp.pro || '',
          organization: emp.orgNamePath || '',
          role: 'user',
          permissions: [],
          empNo: emp.employeeNO || empNo,
        }
      }
      
      return null
    } catch (err) {
      console.error('[UdsValidator] HR API call failed:', err.message)
      return null
    }
  }

  /**
   * Build user context from credentials
   */
  buildUserContext(credentialsOrResponse, isUdsResponse = false) {
    const now = new Date().toISOString()
    
    let userData
    if (isUdsResponse) {
      userData = credentialsOrResponse
    } else {
      userData = {
        userId: credentialsOrResponse.empNo,
        username: credentialsOrResponse.username || credentialsOrResponse.empNo,
        displayName: credentialsOrResponse.displayName || credentialsOrResponse.username || credentialsOrResponse.empNo,
        department: credentialsOrResponse.department || '',
        organization: credentialsOrResponse.organization || '',
        email: credentialsOrResponse.email || '',
        phone: credentialsOrResponse.phone || '',
        empNo: credentialsOrResponse.empNo,
        token: credentialsOrResponse.token,
        lang: credentialsOrResponse.lang,
      }
    }
    
    return {
      userId: userData.userId || userData.empno || userData.empNo || '',
      username: userData.username || userData.name || userData.empNo || userData.empno || '',
      displayName: userData.displayName || userData.username || userData.name || '',
      department: userData.department || userData.dept || '',
      organization: userData.organization || userData.org || '',
      role: userData.role || 'user',
      permissions: userData.permissions || [],
      email: userData.email || '',
      phone: userData.phone || '',
      empNo: userData.empNo || userData.empno || '',
      token: userData.token || '',
      lang: userData.lang || 'zh-CN',
      authenticatedAt: now,
      lastActiveAt: now,
      sessionCreatedAt: now,
      isAuthenticated: true,
      authMode: this.authMode || 'token+profile',
    }
  }

  /**
   * Build error response
   */
  buildUnauthResponse(loginUrl) {
    return {
      code: 401,
      message: 'UDS authentication required',
      login_url: loginUrl,
    }
  }
}
