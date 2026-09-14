/**
 * Classify & prune empty/invalid DSH sessions under ~/.dsh/sessions.
 *
 * empty/shell — log exists but has no user/message and no turn/start
 *               (only session header + permission/sandbox/approval/end-seed)
 * invalid     — no log, 0 bytes, corrupt, non-session header
 * keep        — has at least one conversational event
 *
 * Usage:
 *   node prune-empty-sessions.cjs --dry-run
 *   node prune-empty-sessions.cjs --apply
 */
const fs = require('fs')
const path = require('path')
const { promisify } = require('util')
const { zstdDecompress } = require('zlib')
const zstdDecompressAsync = promisify(zstdDecompress)

const SESSIONS_ROOT = 'C:/Users/zhout/.dsh/sessions'
const WORKSPACE_PATH = 'C:/Users/zhout/.dsh/storages/workspace.json'
const OWNERS_PATH = 'D:/project/chatgpt/oclaw/uds-auth/session-owners.json'
const PROJCACHE = 'C:/Users/zhout/.dsh/storages/session_projcache/sessions'

const ZSTD_MAGIC = 0xfd2fb528
const apply = process.argv.includes('--apply')

/** Event types that prove the session had real conversation activity. */
const LIVE_TYPES = new Set([
  'user/message',
  'turn/start',
  'assistant/message',
  'agent/message',
  'step/start',
])

function scanZstdFrames(buffer, maxFrames = Infinity) {
  const frames = []
  let offset = 0
  while (offset < buffer.length) {
    const start = offset
    if (buffer.length - offset < 4) return { frames, tornStart: start }
    if (buffer.readUInt32LE(offset) !== ZSTD_MAGIC) {
      throw new Error(`invalid magic at ${offset}`)
    }
    offset += 4
    if (offset === buffer.length) return { frames, tornStart: start }
    const descriptor = buffer.readUInt8(offset)
    offset += 1
    if ((descriptor & 0x18) !== 0) throw new Error('reserved frame-header bit')
    const contentSizeFlag = descriptor >>> 6
    const singleSegment = (descriptor & 0x20) !== 0
    const checksum = (descriptor & 0x04) !== 0
    const dictionaryFlag = descriptor & 0x03
    const dictionaryBytes = dictionaryFlag === 3 ? 4 : dictionaryFlag
    const contentSizeBytes =
      contentSizeFlag === 0 ? (singleSegment ? 1 : 0) : 1 << contentSizeFlag
    const remainingHeaderBytes =
      (singleSegment ? 0 : 1) + dictionaryBytes + contentSizeBytes
    if (buffer.length - offset < remainingHeaderBytes) return { frames, tornStart: start }
    offset += remainingHeaderBytes
    for (;;) {
      if (buffer.length - offset < 3) return { frames, tornStart: start }
      const blockHeader = buffer.readUIntLE(offset, 3)
      offset += 3
      const lastBlock = (blockHeader & 1) !== 0
      const blockType = (blockHeader >>> 1) & 0x03
      const blockSize = blockHeader >>> 3
      if (blockType === 0x03) throw new Error('reserved block type')
      const payloadBytes = blockType === 0x01 ? 1 : blockSize
      if (buffer.length - offset < payloadBytes) return { frames, tornStart: start }
      offset += payloadBytes
      if (lastBlock) break
    }
    if (checksum) {
      if (buffer.length - offset < 4) return { frames, tornStart: start }
      offset += 4
    }
    frames.push({ start, end: offset })
    if (frames.length >= maxFrames) return { frames }
  }
  return { frames }
}

function findLog(dir) {
  const names = fs.readdirSync(dir)
  const preferred = names
    .filter((n) => /^session(\.v\d+)?\.jsonl(\.zstd)?$/.test(n))
    .sort()
  return preferred[0] ? path.join(dir, preferred[0]) : null
}

function collectTypesFromText(text, types) {
  for (const line of text.split(/\n/)) {
    if (!line.trim()) continue
    try {
      const o = JSON.parse(line)
      if (o && typeof o.type === 'string') types.add(o.type)
    } catch {
      // ignore bad lines
    }
  }
}

async function classify(dir) {
  const log = findLog(dir)
  if (!log) return { kind: 'invalid', reason: 'no-log' }
  const buf = fs.readFileSync(log)
  if (buf.length === 0) return { kind: 'invalid', reason: 'zero-bytes' }

  const types = new Set()
  try {
    if (log.endsWith('.zstd')) {
      const { frames, tornStart } = scanZstdFrames(buf)
      if (frames.length === 0) {
        return { kind: 'invalid', reason: tornStart != null ? 'torn-frame' : 'no-frames' }
      }
      for (const fr of frames) {
        const plain = await zstdDecompressAsync(buf.subarray(fr.start, fr.end))
        collectTypesFromText(plain.toString('utf8'), types)
        // Early exit once we know it's live
        for (const t of LIVE_TYPES) {
          if (types.has(t)) {
            return { kind: 'keep', reason: `has:${t}`, types: [...types] }
          }
        }
      }
    } else {
      collectTypesFromText(buf.toString('utf8'), types)
    }
  } catch (e) {
    return { kind: 'invalid', reason: `decode:${e.message}` }
  }

  if (!types.has('session')) {
    return { kind: 'invalid', reason: 'non-session-header', types: [...types] }
  }

  for (const t of LIVE_TYPES) {
    if (types.has(t)) return { kind: 'keep', reason: `has:${t}`, types: [...types] }
  }

  return {
    kind: 'empty',
    reason: 'no-conversation',
    types: [...types],
  }
}

async function main() {
  const results = { invalid: [], empty: [], keep: [] }

  for (const proj of fs.readdirSync(SESSIONS_ROOT, { withFileTypes: true })) {
    if (!proj.isDirectory()) continue
    const projDir = path.join(SESSIONS_ROOT, proj.name)
    for (const sid of fs.readdirSync(projDir, { withFileTypes: true })) {
      if (!sid.isDirectory()) continue
      const dir = path.join(projDir, sid.name)
      const c = await classify(dir)
      results[c.kind].push({
        id: sid.name,
        proj: proj.name,
        dir,
        reason: c.reason,
        types: c.types,
      })
    }
  }

  const byProj = {}
  for (const item of [...results.empty, ...results.invalid]) {
    byProj[item.proj] = (byProj[item.proj] || 0) + 1
  }

  console.log(
    JSON.stringify(
      {
        mode: apply ? 'apply' : 'dry-run',
        counts: {
          invalid: results.invalid.length,
          empty: results.empty.length,
          keep: results.keep.length,
          deleteTotal: results.invalid.length + results.empty.length,
        },
        deleteByProject: byProj,
        sampleEmpty: results.empty.slice(0, 5).map((x) => ({
          id: x.id,
          reason: x.reason,
          types: x.types,
        })),
      },
      null,
      2,
    ),
  )

  if (!apply) {
    console.log('\nRe-run with --apply to delete invalid+empty and update workspace/owners.')
    return
  }

  const toDelete = [...results.invalid, ...results.empty]
  const deleteIds = new Set(toDelete.map((x) => x.id))

  for (const item of toDelete) {
    fs.rmSync(item.dir, { recursive: true, force: true })
    const cache = path.join(PROJCACHE, `${item.id}.json`)
    if (fs.existsSync(cache)) fs.rmSync(cache, { force: true })
  }

  if (fs.existsSync(WORKSPACE_PATH)) {
    const bak = WORKSPACE_PATH + '.bak-before-prune-empty'
    fs.copyFileSync(WORKSPACE_PATH, bak)
    const w = JSON.parse(fs.readFileSync(WORKSPACE_PATH, 'utf8'))
    if (Array.isArray(w.global?.archivedSessionIds)) {
      w.global.archivedSessionIds = w.global.archivedSessionIds.filter((id) => !deleteIds.has(id))
    }
    for (const row of Object.values(w.tables?.workspaces || {})) {
      if (!Array.isArray(row.sessionIds)) continue
      const before = row.sessionIds.length
      row.sessionIds = row.sessionIds.filter((id) => !deleteIds.has(id))
      if (row.sessionIds.length !== before) row.updatedAt = new Date().toISOString()
    }
    fs.writeFileSync(WORKSPACE_PATH, JSON.stringify(w, null, 2) + '\n')
    console.log('updated workspace.json; backup', bak)
  }

  if (fs.existsSync(OWNERS_PATH)) {
    const bak = OWNERS_PATH + '.bak-before-prune-empty'
    fs.copyFileSync(OWNERS_PATH, bak)
    const o = JSON.parse(fs.readFileSync(OWNERS_PATH, 'utf8'))
    let removed = 0
    if (o.owners && typeof o.owners === 'object') {
      for (const id of deleteIds) {
        if (Object.prototype.hasOwnProperty.call(o.owners, id)) {
          delete o.owners[id]
          removed++
        }
      }
    }
    fs.writeFileSync(OWNERS_PATH, JSON.stringify(o, null, 2) + '\n')
    console.log('updated session-owners.json removed', removed, 'backup', bak)
  }

  console.log('deleted dirs', toDelete.length)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
