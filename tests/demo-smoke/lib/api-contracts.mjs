import fs from 'node:fs'
import path from 'node:path'
import Ajv2020 from 'ajv/dist/2020.js'
import addFormats from 'ajv-formats'
import { repoRoot, assert } from './category-kit.mjs'

// 统一注册跨文件引用，禁止因只编译envelope而漏掉payload/Citation约束。
export function contractValidator() {
  const ajv = new Ajv2020({ allErrors: true, allowUnionTypes: true }); addFormats(ajv)
  for (const name of fs.readdirSync(path.join(repoRoot, 'contracts')).filter(name => name.endsWith('_v1.json'))) {
    ajv.addSchema(JSON.parse(fs.readFileSync(path.join(repoRoot, 'contracts', name))), 'https://sesrag.local/contracts/' + name)
  }
  return ajv
}
export function validateContract(ajv, name, value) {
  const validate = ajv.getSchema('https://sesrag.local/contracts/' + name)
  assert.ok(validate, '未登记契约：' + name)
  assert.ok(validate(value), `响应违反${name}：${ajv.errorsText(validate.errors)}`)
}
