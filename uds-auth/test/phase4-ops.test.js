/**
 * Phase-4 ops tests (SEC-23/25 fragments).
 */
import assert from 'node:assert/strict'
import test from 'node:test'
import { Readable } from 'node:stream'
import { readBodyLimited, readJsonBodyLimited } from '../lib/utils/read-body.js'
import { RateLimiter } from '../lib/utils/rate-limit.js'
import { audit, redactValue } from '../lib/utils/audit-log.js'

function fakeReq(chunks) {
  return Readable.from(chunks)
}

test('SEC-23: readBodyLimited rejects oversized payload', async () => {
  const big = Buffer.alloc(1024, 0x61)
  await assert.rejects(
    () => readBodyLimited(fakeReq([big, big]), { maxBytes: 1500 }),
    (err) => err.code === 'payload_too_large',
  )
})

test('SEC-23: readJsonBodyLimited parses small JSON', async () => {
  const req = fakeReq([Buffer.from('{"a":1}')])
  assert.deepEqual(await readJsonBodyLimited(req, { maxBytes: 100 }), { a: 1 })
})

test('SEC-23: RateLimiter eventually blocks and cleans buckets', () => {
  const lim = new RateLimiter({ windowMs: 60_000, max: 3 })
  assert.equal(lim.allow('ip1'), true)
  assert.equal(lim.allow('ip1'), true)
  assert.equal(lim.allow('ip1'), true)
  assert.equal(lim.allow('ip1'), false)
  assert.equal(lim.allow('ip2'), true)
  lim.dispose()
})

test('SEC-25: audit redacts secrets and returns structured row', () => {
  const lines = []
  const row = audit({
    action: 'test',
    decision: 'deny',
    reasonCode: 'x',
    actor: 'u1',
    meta: { token: 'secret-value', nested: { password: 'p' }, ok: 'fine' },
  }, {
    logger: {
      warn(s) { lines.push(s) },
      info() {},
    },
  })
  assert.equal(row.type, 'uds-auth.audit')
  assert.equal(row.meta.token, '[redacted]')
  assert.equal(row.meta.nested.password, '[redacted]')
  assert.equal(row.meta.ok, 'fine')
  assert.equal(lines.length, 1)
  assert.equal(lines[0].includes('secret-value'), false)
})

test('SEC-25: redactValue truncates long strings', () => {
  const long = 'x'.repeat(100)
  const out = redactValue(long)
  assert.ok(String(out).includes('…'))
  assert.equal(String(out).includes(long), false)
})
