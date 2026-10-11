import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { MemoryStore } from '../lib/session/memory-store.js'
import { createSessionStore } from '../lib/session/factory.js'

const quiet = { info() {}, warn() {} }

async function freshDir() {
  return mkdtemp(join(tmpdir(), 'uds-sessions-'))
}

async function openStore(dir) {
  const store = new MemoryStore({ file: join(dir, 'sessions.json'), dataDir: dir, logger: quiet })
  await store.init()
  return store
}

test('sessions survive a Host restart (emergency login stays logged in)', async () => {
  const dir = await freshDir()
  try {
    const a = await openStore(dir)
    const { bearer, sessionId } = await a.create({
      empNo: 'administrator',
      authMode: 'local-admin-unlock',
      displayName: 'Local Admin',
    }, 1800)
    await a.flush()
    await a.clear()

    const b = await openStore(dir)
    const row = b.getByBearerSync(bearer)
    assert.equal(row?.sessionId, sessionId)
    assert.equal(row?.empNo, 'administrator')
    assert.equal(row?.kind, 'sealed_box')
    assert.equal(row?.userData.displayName, 'Local Admin')
    assert.equal((await b.getProfile('administrator'))?.displayName, 'Local Admin')
    assert.equal(b.getByBearerSync('f'.repeat(64)), null)
    await b.clear()
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('disk holds only the bearer hash; userData (UAC token) is encrypted', async () => {
  const dir = await freshDir()
  try {
    const a = await openStore(dir)
    const { bearer } = await a.create({ empNo: '1001', token: 'UAC-SECRET-TOKEN', email: 'x@example.test' }, 1800)
    await a.flush()
    const disk = await readFile(join(dir, 'sessions.json'), 'utf-8')
    assert.equal(disk.includes(bearer), false, 'raw bearer never written')
    assert.equal(disk.includes('UAC-SECRET-TOKEN'), false, 'token not in clear')
    assert.equal(disk.includes('x@example.test'), false, 'profile fields not in clear')
    await a.clear()
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('expired and tampered rows are dropped on load', async () => {
  const dir = await freshDir()
  try {
    const a = await openStore(dir)
    const live = await a.create({ empNo: 'u1' }, 1800)
    const dead = await a.create({ empNo: 'u2' }, 1800)
    const forged = await a.create({ empNo: 'u3' }, 1800)
    await a.flush()
    await a.clear()

    const file = join(dir, 'sessions.json')
    const data = JSON.parse(await readFile(file, 'utf-8'))
    for (const row of data.sessions) {
      if (row.sessionId === dead.sessionId) row.expiresAt = Date.now() - 1
      if (row.sessionId === forged.sessionId) row.userData = row.userData.slice(0, -4) + 'AAAA'
    }
    await writeFile(file, JSON.stringify(data))

    const b = await openStore(dir)
    assert.ok(b.getByBearerSync(live.bearer))
    assert.equal(b.getByBearerSync(dead.bearer), null)
    assert.equal(b.getByBearerSync(forged.bearer), null)
    await b.clear()
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('revocation (logout) is persisted', async () => {
  const dir = await freshDir()
  try {
    const a = await openStore(dir)
    const { bearer } = await a.create({ empNo: 'administrator', authMode: 'fallback-password' }, 1800)
    await a.revokeBearer(bearer)
    await a.flush()
    await a.clear()
    const b = await openStore(dir)
    assert.equal(b.getByBearerSync(bearer), null)
    await b.clear()
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})

test('factory wires persistence; no file configured keeps pure in-memory behavior', async () => {
  const dir = await freshDir()
  try {
    const persisted = await createSessionStore({ storeType: 'memory' }, {
      file: join(dir, 'sessions.json'), dataDir: dir, logger: quiet,
    })
    const { bearer } = await persisted.create({ empNo: 'u1' }, 1800)
    await persisted.flush()
    await persisted.clear()
    const again = await createSessionStore({ storeType: 'memory' }, {
      file: join(dir, 'sessions.json'), dataDir: dir, logger: quiet,
    })
    assert.ok(again.getByBearerSync(bearer))
    await again.clear()

    const plain = await createSessionStore({ storeType: 'memory' })
    await plain.create({ empNo: 'u1' }, 1800)
    await plain.flush()
    await plain.clear()
  } finally {
    await rm(dir, { recursive: true, force: true })
  }
})
