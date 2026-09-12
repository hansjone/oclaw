import { describe, it, after } from 'node:test'
import assert from 'node:assert/strict'
import {
  LOCAL_ADMIN_BOX_ENV,
  LOCAL_ADMIN_ENV,
  sealLocalAdminBox,
  openLocalAdminBox,
  isLocalAdminBoxConfigured,
  readLocalAdminBox,
} from '../lib/local-admin.js'

describe('local-admin sealed box', () => {
  const prevBox = process.env[LOCAL_ADMIN_BOX_ENV]
  const prevKey = process.env[LOCAL_ADMIN_ENV]

  after(() => {
    if (prevBox === undefined) delete process.env[LOCAL_ADMIN_BOX_ENV]
    else process.env[LOCAL_ADMIN_BOX_ENV] = prevBox
    if (prevKey === undefined) delete process.env[LOCAL_ADMIN_ENV]
    else process.env[LOCAL_ADMIN_ENV] = prevKey
  })

  it('seal + open with correct passphrase', () => {
    const passphrase = 'my-local-secret-key'
    const box = sealLocalAdminBox(passphrase)
    assert.ok(box.length > 40)
    const ok = openLocalAdminBox(box, passphrase)
    assert.equal(ok.ok, true)
    assert.equal(ok.empNo, 'administrator')
  })

  it('wrong passphrase fails decrypt', () => {
    const box = sealLocalAdminBox('correct-passphrase-xx')
    const bad = openLocalAdminBox(box, 'wrong-passphrase-yyy')
    assert.equal(bad.ok, false)
    assert.equal(bad.reason, 'decrypt_failed')
  })

  it('env box alone does not imply auto-login; only configures unlock', () => {
    delete process.env[LOCAL_ADMIN_BOX_ENV]
    assert.equal(isLocalAdminBoxConfigured(), false)

    const box = sealLocalAdminBox('another-strong-key')
    process.env[LOCAL_ADMIN_BOX_ENV] = box
    assert.equal(isLocalAdminBoxConfigured(), true)
    assert.equal(readLocalAdminBox(), box)

    // Old KEY env must not unlock without decrypt
    process.env[LOCAL_ADMIN_ENV] = 'aaaaaaaaaaaaaaaa'
    const stillNeedDecrypt = openLocalAdminBox(box, process.env[LOCAL_ADMIN_ENV])
    assert.equal(stillNeedDecrypt.ok, false)
  })
})
