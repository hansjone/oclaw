import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { classifyNetworkError, hostOfUrl } from '../lib/utils/net-error.js'
import { apiError, MESSAGES } from '../lib/i18n.js'
import { readFileSync } from 'node:fs'

const CODES = [
  'upstream_dns', 'upstream_timeout', 'upstream_unreachable', 'upstream_cert', 'upstream_error',
  'upstream_http_status', 'invalid_upstream_response', 'profile_http_status', 'profile_rejected',
  'login_finalize_failed',
]

describe('classifyNetworkError', () => {
  it('maps errno/TLS codes to actionable api codes', () => {
    assert.equal(classifyNetworkError({ code: 'ENOTFOUND' }), 'upstream_dns')
    assert.equal(classifyNetworkError({ code: 'EAI_AGAIN' }), 'upstream_dns')
    assert.equal(classifyNetworkError({ code: 'ETIMEDOUT' }), 'upstream_timeout')
    assert.equal(classifyNetworkError({ message: 'directRequest timeout after 3000ms: x' }), 'upstream_timeout')
    assert.equal(classifyNetworkError({ code: 'ECONNREFUSED' }), 'upstream_unreachable')
    assert.equal(classifyNetworkError({ message: 'socket hang up' }), 'upstream_unreachable')
    assert.equal(classifyNetworkError({ code: 'UNABLE_TO_VERIFY_LEAF_SIGNATURE' }), 'upstream_cert')
    assert.equal(classifyNetworkError({ code: 'SELF_SIGNED_CERT_IN_CHAIN' }), 'upstream_cert')
    assert.equal(classifyNetworkError({ message: 'unable to get local issuer certificate' }), 'upstream_cert')
    assert.equal(classifyNetworkError({ code: 'WHATEVER' }), 'upstream_error')
    assert.equal(classifyNetworkError(null), 'upstream_error')
  })

  it('extracts host without throwing', () => {
    assert.equal(hostOfUrl('https://icenterapi.zte.com.cn/a/b'), 'icenterapi.zte.com.cn')
    assert.equal(hostOfUrl('not a url'), '')
  })
})

describe('upstream error messages', () => {
  it('are defined in zh and en and interpolate host', () => {
    for (const code of CODES) {
      assert.ok(MESSAGES.zh['err.' + code], 'zh ' + code)
      assert.ok(MESSAGES.en['err.' + code], 'en ' + code)
    }
    const m = apiError('upstream_dns', 'zh', { host: 'uac.zte.com.cn' })
    assert.equal(m.error, 'upstream_dns')
    assert.match(m.message, /uac\.zte\.com\.cn/)
  })

  it('are mirrored in the browser client dictionary', () => {
    const client = readFileSync(new URL('../lib/client.js', import.meta.url), 'utf8')
    for (const code of CODES) {
      assert.equal(client.split(`"err.${code}":`).length - 1, 2, code)
    }
  })

  it('bootstrap_required names the scanned employee number and the way out', () => {
    for (const locale of ['zh', 'en']) {
      const m = apiError('bootstrap_required', locale, { empNo: '10012345' })
      assert.equal(m.error, 'bootstrap_required')
      assert.match(m.message, /UDS_AUTH_INITIAL_ADMIN=10012345/)
      assert.doesNotMatch(m.message, /\{empNo\}/)
    }
  })
})
