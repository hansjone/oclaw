#!/usr/bin/env node
/**
 * Generate UDS_AUTH_LOCAL_ADMIN_BOX for local decrypt-to-unlock admin.
 *
 * Usage:
 *   node scripts/seal-local-admin.mjs "your-passphrase-here"
 *
 * Then set the printed env on the Harness process (keep the passphrase offline).
 */
import { sealLocalAdminBox, LOCAL_ADMIN_BOX_ENV } from '../lib/local-admin.js'

const passphrase = process.argv[2]
if (!passphrase) {
  console.error('Usage: node scripts/seal-local-admin.mjs "<passphrase>"')
  process.exit(1)
}

try {
  const box = sealLocalAdminBox(passphrase)
  console.log(`# Keep the passphrase secret. Only the box goes into the process env.`)
  console.log(`${LOCAL_ADMIN_BOX_ENV}=${box}`)
} catch (err) {
  console.error(err.message || err)
  process.exit(1)
}
