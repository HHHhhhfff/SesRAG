import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { assert, execute } from '../lib/category-kit.mjs'
import { processIdentity, sameProcess, stopOwnedProcess } from '../lib/process-identity.mjs'

// 仅正式父入口调用：先核验本run和精确标签，所有失败均保留runtime并非零退出。
export function cleanupRegistered(runtime, runId, project) {
  const observations = [], errors = []
  const read = name => {
    const file = path.join(runtime, name)
    if (!fs.existsSync(file)) return null
    const data = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))
    assert.equal(data.schema_version, 1); assert.equal(data.parent_run_id, runId); assert.equal(data.project, project)
    return { file, data }
  }
  for (const name of ['process-resources.json', 'frontend-resources.json']) {
    try {
      const registry = read(name)
      if (!registry) continue
      for (const row of registry.data.resources) {
        if (row.status === 'closed') continue
        try {
          // owner关闭同时关闭其Vite/HTTP/SSE socket；浏览器服务另有独立身份。
          for (const identity of [row.process_identity, row.owner_identity].filter(Boolean)) {
            if (identity.pid === process.pid) continue
            observations.push(stopOwnedProcess(identity))
          }
          assert.ok(row.process_identity || row.owner_identity, '旧登记缺少进程身份，需保留待人工核验')
          for (const identity of [row.process_identity, row.owner_identity].filter(Boolean)) assert.ok(!sameProcess(identity, processIdentity(identity.pid)))
          row.status = 'closed'; row.recovered = true
        } catch (error) { errors.push({ registry: name, id: row.id, error: error.message }) }
      }
      fs.writeFileSync(registry.file, JSON.stringify(registry.data, null, 2))
    } catch (error) { errors.push({ registry: name, error: error.message }) }
  }
  try {
    const registry = read('execution-resources.json')
    if (registry) {
      // 一次只读名称列表，随后只检查登记的精确名字及标签；不把已closed状态当作实际消失。
      const inventory = execute('docker', ['ps','-a','--format','{{.Names}}'])
      assert.equal(inventory.code,0)
      const present = new Set(inventory.stdout.trim().split(/\r?\n/).filter(Boolean))
      for (const row of registry.data.containers) {
        try {
          assert.equal(row.project, project); assert.equal(row.parent_run_id, runId)
          assert.match(row.name, new RegExp('^' + project + '-5a-[a-f0-9]{8}$'))
          if (present.has(row.name)) {
            const inspect = execute('docker', ['inspect', row.name, '--format', '{{json .Config.Labels}}'])
            assert.equal(inspect.code, 0)
            const labels = JSON.parse(inspect.stdout)
            assert.equal(labels['com.docker.compose.project'], project)
            assert.equal(labels['sesrag.smoke.run_id'], runId)
            assert.equal(labels['sesrag.smoke.purpose'], 'execution-harness')
            assert.equal(execute('docker', ['rm', '-f', row.name]).code, 0)
            const after = execute('docker', ['ps', '-a', '--filter', `name=^/${row.name}$`, '--format', '{{.ID}}'])
            assert.equal(after.code, 0); assert.equal(after.stdout.trim(), '')
          }
          row.status = 'closed'; row.recovered = true
          observations.push({ container: row.name, absent: true })
        } catch (error) { errors.push({ container: row.name, error: error.message }) }
      }
      fs.writeFileSync(registry.file, JSON.stringify(registry.data, null, 2))
    }
  } catch (error) { errors.push({ registry: 'execution-resources.json', error: error.message }) }
  return { status: errors.length ? 'failed' : 'passed', observations, errors }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const result = cleanupRegistered(...process.argv.slice(2))
  process.stdout.write(JSON.stringify(result))
  process.exitCode = result.status === 'passed' ? 0 : 1
}
