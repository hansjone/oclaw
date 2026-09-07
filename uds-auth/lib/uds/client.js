/**
 * UDS (Unified Authentication Service) client
 * Handles communication with UDS verification endpoint
 */
export class UdsClient {
  /**
   * @param {object} config - UDS configuration
   * @param {string} config.baseUrl - UDS base URL (e.g., https://uac.zte.com.cn)
   * @param {string} config.systemCode - Business system code
   * @param {number} config.timeout - Request timeout in milliseconds
   */
  constructor(config) {
    if (!config.baseUrl) {
      throw new Error('UDS client requires baseUrl')
    }
    
    this.baseUrl = config.baseUrl
    this.systemCode = config.systemCode || ''
    this.timeout = config.timeout || 5000
  }

  /**
   * Build UDS verification URL
   * @param {string} token - UDS authentication token
   * @param {string} empNo - Employee number
   * @returns {string} Verification URL
   */
  buildVerificationUrl(token, empNo) {
    // Based on frontend analysis: UDS uses token-based verification
    // TODO: Confirm exact UDS API endpoint with UDS team
    const params = new URLSearchParams({
      token: token,
      system_code: this.systemCode,
      action: 'verify',
    })
    
    if (empNo) {
      params.append('emp_no', empNo)
    }
    
    return `${this.baseUrl}/api/auth/verify?${params.toString()}`
  }

  /**
   * Verify UDS token and retrieve user information
   * @param {string} token - UDS authentication token
   * @param {string} empNo - Employee number (optional)
   * @returns {Promise<object>} User context object
   * @throws {Error} When verification fails
   */
  async verifyToken(token, empNo = '') {
    const url = this.buildVerificationUrl(token, empNo)
    
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeout)
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(`UDS verification failed: ${errorData.msg || response.statusText}`)
      }
      
      const data = await response.json()
      
      // Parse UDS response into standard user context format
      return this.parseUdsResponse(data)
    } catch (err) {
      clearTimeout(timeoutId)
      
      if (err.name === 'AbortError') {
        throw new Error('UDS verification timeout')
      }
      
      throw err
    }
  }

  /**
   * Parse UDS response into user context object
   * @param {object} data - Raw UDS response
   * @returns {object} Standardized user context
   */
  parseUdsResponse(data) {
    // Adjust field mapping based on actual UDS response structure
    const userData = data.data || data
    
    return {
      userId: userData.empno || userData.user_id || '',
      username: userData.username || userData.name || '',
      displayName: userData.display_name || userData.username || '',
      department: userData.dept || userData.department || '',
      organization: userData.org || userData.organization || '',
      role: userData.role || 'user',
      permissions: userData.permissions || [],
      email: userData.email || '',
      phone: userData.phone || '',
    }
  }
}
