/**
 * Bundle `qrcode` (SVG path) into lib/qrcode-bundled.cjs so Desktop tgz
 * installs need no npm registry fetch for dependencies.
 *
 * Usage: bun run scripts/bundle-qrcode.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const entry = join(root, 'scripts', 'qrcode-entry.cjs')
const out = join(root, 'lib', 'qrcode-bundled.cjs')

mkdirSync(dirname(out), { recursive: true })

const result = await Bun.build({
  entrypoints: [entry],
  outfile: out,
  target: 'node',
  format: 'cjs',
  sourcemap: 'none',
  minify: false,
})

if (!result.success) {
  console.error(result.logs)
  throw new Error('bundle qrcode failed')
}

// Bun may write via outfile; also ensure content if outputs differ.
if (result.outputs[0]) {
  writeFileSync(out, await result.outputs[0].text(), 'utf8')
}
console.log(`wrote ${out}`)
