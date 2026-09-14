const fs = require('fs')
const path = require('path')

const workspacePath = 'C:/Users/zhout/.dsh/storages/workspace.json'
const sessionsRoot = 'C:/Users/zhout/.dsh/sessions'

const map = {
  '--C-Users-zhout-.dsh-user-workspaces-administrator--':
    'C:\\Users\\zhout\\.dsh\\user-workspaces\\administrator',
  '--D-project-chatgpt--': 'D:\\project\\chatgpt',
  '--D-project-harness--': 'D:\\project\\harness',
}

const w = JSON.parse(fs.readFileSync(workspacePath, 'utf8'))
const pathToId = {}
for (const [id, row] of Object.entries(w.tables.workspaces)) {
  pathToId[row.path] = id
}

let added = 0
for (const [folder, wsPath] of Object.entries(map)) {
  const wsId = pathToId[wsPath]
  if (!wsId) {
    console.log('skip no workspace', wsPath)
    continue
  }
  const proj = path.join(sessionsRoot, folder)
  if (!fs.existsSync(proj)) continue
  const disk = fs
    .readdirSync(proj, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
  const row = w.tables.workspaces[wsId]
  const existing = new Set(row.sessionIds || [])
  const missing = disk.filter((id) => !existing.has(id))
  added += missing.length
  row.sessionIds = [...missing, ...(row.sessionIds || [])]
  row.updatedAt = new Date().toISOString()
  console.log(wsPath, 'disk', disk.length, 'now', row.sessionIds.length, 'added', missing.length)
}

fs.copyFileSync(workspacePath, workspacePath + '.bak-before-session-restore')
fs.writeFileSync(workspacePath, JSON.stringify(w, null, 2) + '\n')
console.log('added', added)
