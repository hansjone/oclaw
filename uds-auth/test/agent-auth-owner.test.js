import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createAgentAuthHandlers } from '../lib/agent-auth.js'

const makeRes = () => ({
  statusCode: 0, headers: {}, body: '',
  setHeader(k, v) { this.headers[k] = v },
  end(s) { this.body = s },
})
const loopbackReq = (payload) => ({
  method: 'POST',
  socket: { remoteAddress: '127.0.0.1' },
  headers: { 'content-type': 'application/json', 'x-dsh-session-id': 's1' },
  async *[Symbol.asyncIterator]() { yield Buffer.from(JSON.stringify(payload)) },
})

function handlersFor(owner, creds) {
  return createAgentAuthHandlers({
    resolveCredentialsForSession: async () => creds,
    getSessionOwner: () => owner,
    resolveCallerSession: async () => ({ empNo: owner }),
    outboundHosts: ['icenterapi.zte.com.cn'],
  })
}

test('skill outbound on an emergency-owned session names the owner and the way out', async () => {
  const res = makeRes()
  await handlersFor('administrator', null).handleOutbound(
    loopbackReq({ url: 'https://icenterapi.zte.com.cn/x' }), res)
  assert.equal(res.statusCode, 401)
  const body = JSON.parse(res.body)
  assert.equal(body.error, 'session_owner_no_uac')
  assert.match(body.message, /administrator/)
  assert.doesNotMatch(body.message, /\{owner\}/)
})

test('skill outbound for a UAC owner with no cached token keeps no_skill_credentials, with owner', async () => {
  const res = makeRes()
  await handlersFor('10329667', null).handleOutbound(
    loopbackReq({ url: 'https://icenterapi.zte.com.cn/x' }), res)
  assert.equal(res.statusCode, 401)
  const body = JSON.parse(res.body)
  assert.equal(body.error, 'no_skill_credentials')
  assert.match(body.message, /10329667/)
})

test('credentials never cross owners: another account\'s token is refused', async () => {
  const res = makeRes()
  await handlersFor('10329667', { empNo: '99999999', token: 't' }).handleOutbound(
    loopbackReq({ url: 'https://icenterapi.zte.com.cn/x' }), res)
  assert.equal(res.statusCode, 401)
  assert.equal(JSON.parse(res.body).error, 'no_skill_credentials')
})
