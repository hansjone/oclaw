#!/usr/bin/env node
/**
 * SEC-24: verify npm pack file list before publish.
 * Usage: node scripts/pack-check.mjs
 */
import { execSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const forbidden = [
  /(?:^|\/)node_modules\//,
  /(?:^|\/)__pycache__\//,
  /\.pyc$/,
  /(?:^|\/)skill-credentials\.json$/,
  /(?:^|\/)session-bridge\.json$/,
  /(?:^|\/)session-owners\.json/,
  /(?:^|\/)user-workspaces\.json$/,
  /(?:^|\/)roles\.json$/,
  /(?:^|\/)config\.runtime\.json$/,
  /\.uds-auth-secret-key$/,
  /\.tgz$/,
]

const required = [
  'package.json',
  'LICENSE',
  'lib/index.js',
  'lib/qrcode-bundled.cjs',
  'scripts/seal-local-admin.mjs',
  'skills/uds-skill-auth/scripts/uds_skill_auth.py',
  'skill-helpers/python/uds_skill_auth.py',
  'README.md',
  'README.zh.md',
  'docs/sbom.cdx.json',
  'docs/THIRD-PARTY-NOTICES.txt',
  'docs/upgrade-0.3.10.zh.md',
  'docs/upgrade-0.3.11.zh.md',
  'lib/desktop-bootstrap.js',
]

function listPackFiles() {
  // --ignore-scripts avoids prepack (bun bundle) polluting stdout / requiring bun.
  const raw = execSync('npm pack --dry-run --json --ignore-scripts', {
    cwd: root,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, npm_config_loglevel: 'error' },
  })

  const start = raw.indexOf('[')
  const end = raw.lastIndexOf(']')
  if (start < 0 || end <= start) {
    throw new Error('npm pack --json produced no array')
  }
  const parsed = JSON.parse(raw.slice(start, end + 1))
  const entry = Array.isArray(parsed) ? parsed[0] : parsed
  return (entry?.files || []).map((f) => String(f.path || f).replace(/\\/g, '/'))
}

const files = listPackFiles()
let failed = false

if (!files.length) {
  console.error('[pack-check] empty pack file list')
  process.exit(1)
}

for (const f of files) {
  for (const re of forbidden) {
    if (re.test(f)) {
      console.error('[pack-check] FORBIDDEN in package:', f)
      failed = true
    }
  }
}
for (const need of required) {
  const norm = need.replace(/\\/g, '/')
  const ok = files.some((f) => f === norm || f.endsWith('/' + norm))
  if (!ok && !existsSync(join(root, need))) {
    console.error('[pack-check] MISSING required path on disk:', need)
    failed = true
  } else if (!ok) {
    console.error('[pack-check] MISSING from pack list:', need)
    failed = true
  }
}

const a = readFileSync(join(root, 'skills/uds-skill-auth/scripts/uds_skill_auth.py'), 'utf8')
const b = readFileSync(join(root, 'skill-helpers/python/uds_skill_auth.py'), 'utf8')
if (a !== b) {
  console.error('[pack-check] Python helpers diverged')
  failed = true
}

const sbom = JSON.parse(readFileSync(join(root, 'docs/sbom.cdx.json'), 'utf8'))
const metadata = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
const bundleHash = createHash('sha256').update(readFileSync(join(root, 'lib/qrcode-bundled.cjs'))).digest('hex')
if (sbom.metadata?.component?.version !== metadata.version
  || !sbom.metadata?.properties?.some(p => p.name === 'uds-auth:bundle-sha256' && p.value === bundleHash)) {
  console.error('[pack-check] SBOM version/bundle hash differs; rebuild bundle and SBOM')
  failed = true
}

if (failed) {
  process.exit(1)
}
console.log('[pack-check] OK —', files.length, 'files')
