#!/usr/bin/env node
/**
 * Generate UDS_AUTH_LOCAL_ADMIN_BOX for local decrypt-to-unlock admin.
 *
 * Usage:
 *   node scripts/seal-local-admin.mjs
 *   # prompts for passphrase on stdin (hidden when TTY)
 *   node scripts/seal-local-admin.mjs --stdin   # read one line from stdin
 *
 * Passphrase on argv is rejected (R10) so it does not land in shell history.
 */
import { createInterface } from 'node:readline'
import { stdin as input, stdout as output, stderr } from 'node:process'
import { sealLocalAdminBox, LOCAL_ADMIN_BOX_ENV } from '../lib/local-admin.js'

async function readPassphrase() {
  if (process.argv.includes('--stdin') || !process.stdin.isTTY) {
    const rl = createInterface({ input, crlfDelay: Infinity })
    const line = await new Promise((resolve) => {
      rl.once('line', (l) => resolve(l))
      rl.once('close', () => resolve(''))
    })
    rl.close()
    return String(line || '').replace(/\r$/, '')
  }
  // Interactive: do not echo
  stderr.write('Passphrase (input hidden): ')
  return await new Promise((resolve, reject) => {
    const wasRaw = input.isRaw
    try { input.setRawMode?.(true) } catch { /* ignore */ }
    input.resume()
    let buf = ''
    const onData = (chunk) => {
      const s = chunk.toString('utf8')
      for (const ch of s) {
        if (ch === '\n' || ch === '\r' || ch === '\u0004') {
          cleanup()
          stderr.write('\n')
          resolve(buf)
          return
        }
        if (ch === '\u0003') {
          cleanup()
          reject(new Error('cancelled'))
          return
        }
        if (ch === '\u007f' || ch === '\b') {
          buf = buf.slice(0, -1)
          continue
        }
        buf += ch
      }
    }
    const cleanup = () => {
      input.off('data', onData)
      try { input.setRawMode?.(!!wasRaw) } catch { /* ignore */ }
      input.pause()
    }
    input.on('data', onData)
  })
}

if (process.argv[2] && process.argv[2] !== '--stdin') {
  console.error('Do not pass the passphrase on argv (shell history risk).')
  console.error('Usage: node scripts/seal-local-admin.mjs')
  console.error('   or: echo passphrase | node scripts/seal-local-admin.mjs --stdin')
  process.exit(1)
}

try {
  const passphrase = await readPassphrase()
  if (!passphrase || passphrase.length < 12) {
    console.error('Passphrase required (min 12 characters).')
    process.exit(1)
  }
  const box = sealLocalAdminBox(passphrase)
  console.log('# Keep the passphrase secret. Only the box goes into env and/or profile file.')
  console.log(`${LOCAL_ADMIN_BOX_ENV}=${box}`)
  console.log('# Also durable for Desktop Host (often misses User env after reinstall):')
  console.log(`#   write the box string into %USERPROFILE%\\.uds-auth\\local-admin.box`)
  try {
    const { writeFileSync, mkdirSync } = await import('node:fs')
    const { homedir } = await import('node:os')
    const { join } = await import('node:path')
    const dir = join(homedir(), '.uds-auth')
    mkdirSync(dir, { recursive: true })
    const file = join(dir, 'local-admin.box')
    writeFileSync(file, box + '\n', { encoding: 'utf8', mode: 0o600 })
    console.log(`# Wrote ${file}`)
  } catch (writeErr) {
    console.error('# Could not write ~/.uds-auth/local-admin.box:', writeErr.message || writeErr)
  }
} catch (err) {
  console.error(err.message || err)
  process.exit(1)
}
