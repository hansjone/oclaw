/**
 * Cookie helper utilities
 */

/**
 * Get a specific cookie value from a cookie string
 * @param {string} cookieString - The full cookie header value
 * @param {string} name - The cookie name to extract
 * @returns {string|null} The cookie value or null
 */
export function getCookie(cookieString, name) {
  if (!cookieString) return null
  
  const match = cookieString.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`))
  if (match && match[1]) {
    return decodeURIComponent(match[1])
  }
  return null
}

/**
 * Parse all cookies from a cookie string
 * @param {string} cookieString - The full cookie header value
 * @returns {object} Object with cookie names as keys
 */
export function parseCookies(cookieString) {
  if (!cookieString) return {}
  
  const cookies = {}
  const pairs = cookieString.split(/;\\s*/)
  
  for (const pair of pairs) {
    const [name, ...valueParts] = pair.split('=')
    if (name) {
      cookies[name.trim()] = decodeURIComponent(valueParts.join('='))
    }
  }
  
  return cookies
}
