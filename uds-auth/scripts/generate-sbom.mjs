import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { resolve, join } from 'node:path'
const root = resolve(import.meta.dirname, '..')
const pkg = JSON.parse(await readFile(join(root, 'package.json'), 'utf8'))
const lock = JSON.parse(await readFile(join(root, 'package-lock.json'), 'utf8'))
const bundle = await readFile(join(root, 'lib/qrcode-bundled.cjs'))
// Bun can emit pnpm's virtual-store metadata (node_modules/.pnpm/package.json)
// in its source comments. It is not bundled application code and is not a
// dependency component, so exclude it from the SBOM source inventory.
const sourceFiles = [...bundle.toString().matchAll(/^\/\/ node_modules\/(.+)$/gm)]
  .map(m => m[1].trim())
  .filter(path => path !== '.pnpm/package.json')
if (!sourceFiles.length) throw new Error('bundle source inventory missing')
const names = [...new Set(sourceFiles.map(path => path.startsWith('@') ? path.split('/').slice(0, 2).join('/') : path.split('/')[0]))].sort()
const components = [], notices = []
for (const name of names) {
  const row = lock.packages['node_modules/' + name]
  const manifest = JSON.parse(await readFile(join(root, 'node_modules', name, 'package.json'), 'utf8'))
  if (!row?.integrity || row.version !== manifest.version || !manifest.license) throw new Error('unlocked/unlicensed bundle component: ' + name)
  let license
  for (const file of ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENSE-MIT', 'license']) {
    try { license = await readFile(join(root, 'node_modules', name, file), 'utf8'); break } catch (err) { if (err.code !== 'ENOENT') throw err }
  }
  if (!license) throw new Error('missing third-party license: ' + name)
  notices.push(`${name} ${row.version} (${manifest.license})\n\n${license.trim()}\n`)
  const hashes = []
  for (const file of sourceFiles.filter(file => file.startsWith(name + '/'))) {
    const data = await readFile(join(root, 'node_modules', file))
    hashes.push({ file, sha256: createHash('sha256').update(data).digest('hex') })
  }
  const purl = `pkg:npm/${name.replace('@', '%40')}@${row.version}`
  components.push({ type: 'library', name, version: row.version, purl, 'bom-ref': purl,
    licenses: [{ license: { id: manifest.license } }],
    properties: [{ name: 'uds-auth:delivery', value: 'bundled in lib/qrcode-bundled.cjs' },
      { name: 'npm:integrity', value: row.integrity }, { name: 'uds-auth:source-files', value: JSON.stringify(hashes) }] })
}
const mainRef = `pkg:npm/uds-auth@${pkg.version}`
const bom = { bomFormat: 'CycloneDX', specVersion: '1.5', version: 1,
  metadata: { component: { type: 'application', name: pkg.name, version: pkg.version, 'bom-ref': mainRef,
    licenses: [{ license: { id: pkg.license } }] }, properties: [
    { name: 'uds-auth:bundle-sha256', value: createHash('sha256').update(bundle).digest('hex') },
    { name: 'uds-auth:external-peer', value: 'React supplied by DSH; audit its exact version in the Host SBOM' },
    { name: 'uds-auth:scope', value: 'Actual vendored runtime bundle; development dependency audit is a separate npm audit --include=dev gate' },
  ] }, components, dependencies: [{ ref: mainRef, dependsOn: components.map(c => c['bom-ref']) },
    ...components.map(c => ({ ref: c['bom-ref'], dependsOn: [] }))] }
await mkdir(join(root, 'docs'), { recursive: true })
await writeFile(join(root, 'docs/sbom.cdx.json'), JSON.stringify(bom, null, 2) + '\n')
await writeFile(join(root, 'docs/THIRD-PARTY-NOTICES.txt'), notices.join('\n---\n\n'))
console.log(`SBOM: ${components.length} bundled components, ${sourceFiles.length} source files`)
