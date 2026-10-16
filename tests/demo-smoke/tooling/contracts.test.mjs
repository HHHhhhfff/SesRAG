import fs from 'node:fs'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import Ajv2020 from 'ajv/dist/2020.js'
import addFormats from 'ajv-formats'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

test('Event type/data必须联合校验而非只校验envelope', () => {
  const ajv = new Ajv2020({ allErrors: true }); addFormats(ajv)
  for (const name of fs.readdirSync('contracts').filter(x => x.endsWith('_v1.json'))) ajv.addSchema(JSON.parse(fs.readFileSync('contracts/' + name)), 'https://sesrag.local/contracts/' + name)
  const validate = ajv.getSchema('https://sesrag.local/contracts/run_event_v1.json')
  const event = { schema_version: 1, event_id: '00000000-0000-4000-8000-000000000001', run_id: '00000000-0000-4000-8000-000000000002', seq: 1, type: 'answer.delta', occurred_at: '2026-10-13T00:00:00Z', data: { text: '第一片' } }
  assert.ok(validate(event))
  for (const data of [{}, { text: 42 }, { text: '片', secret: 'sentinel' }, { task_id: event.run_id }]) assert.equal(validate({ ...event, data }), false)
  assert.equal(validate({ ...event, type: 'run.started' }), false)
})

test('类型生成漂移在真实子进程非零失败，不修改正式类型', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(),'sesrag-type-drift-'))
  try {
    fs.cpSync('contracts',path.join(root,'contracts'),{recursive:true})
    fs.mkdirSync(path.join(root,'frontend/scripts'),{recursive:true})
    fs.mkdirSync(path.join(root,'frontend/src/types'),{recursive:true})
    fs.copyFileSync('frontend/scripts/generate-api-types.mjs',path.join(root,'frontend/scripts/generate-api-types.mjs'))
    fs.copyFileSync('frontend/src/types/api.ts',path.join(root,'frontend/src/types/api.ts'))
    const script = path.join(root,'frontend/scripts/generate-api-types.mjs')
    assert.equal(spawnSync(process.execPath,[script,'--check'],{windowsHide:true}).status,0)
    const schema = JSON.parse(fs.readFileSync(path.join(root,'contracts/thread_v1.json')))
    schema.properties.title.type='number'
    fs.writeFileSync(path.join(root,'contracts/thread_v1.json'),JSON.stringify(schema))
    const failed=spawnSync(process.execPath,[script,'--check'],{windowsHide:true,encoding:'utf8'})
    assert.equal(failed.status,1); assert.match(failed.stderr,/API类型与契约漂移/)
  } finally { fs.rmSync(root,{recursive:true}) }
})
