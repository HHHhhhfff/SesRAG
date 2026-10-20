import { readFile, writeFile } from 'node:fs/promises'

// 只支持仓库契约实际使用的JSON Schema子集；未知结构显式失败，不静默生成any。
const v1Names = {
  'thread_v1.json': 'ThreadSummary', 'message_v1.json': 'Message', 'citation_v1.json': 'Citation',
  'evidence_v1.json': 'Evidence', 'document_v1.json': 'DocumentItem', 'run_v1.json': 'RunDetail',
  'run_event_v1.json': 'RunEvent', 'health_v1.json': 'HealthReady', 'api_responses_v1.json': null,
}
const v2Names = {
  'thread_v2.json': 'ThreadSummary', 'branch_v2.json': 'Branch',
  'message_v2.json': 'Message', 'run_v2.json': 'RunDetail',
  'model_profile_v2.json': 'ModelProfile', 'context_plan_v2.json': 'ContextPlan',
  'run_event_v2.json': 'RunEvent', 'api_responses_v2.json': null,
}
const schemas = new Map()
const registered = new Map()
for (const [file, name] of Object.entries({ ...v1Names, ...v2Names })) {
  const schema = JSON.parse(await readFile(new URL(`../../contracts/${file}`, import.meta.url), 'utf8'))
  schemas.set(file, schema)
  if (name) registered.set(`${file}#`, name)
  for (const definition of Object.keys(schema.$defs ?? {})) registered.set(`${file}#/$defs/${definition}`, definition)
}
let activeVersion
let imports

function render(schema, file) {
  if (!Object.keys(schema).length) return 'unknown'
  if (schema.$ref) {
    const [target = '', fragment = ''] = schema.$ref.split('#')
    const key = `${target || file}#${fragment}`
    const name = registered.get(key)
    if (!name) {
      const referred = fragment.split('/').slice(1).reduce((value, part) => value?.[part.replaceAll('~1', '/').replaceAll('~0', '~')], schemas.get(target || file))
      if (!referred) throw new Error(`未登记的Schema引用：${key}`)
      return render(referred, target || file)
    }
    if (activeVersion === 'v2' && (target || file).endsWith('_v1.json')) {
      imports.add(name)
      return `Legacy${name}`
    }
    return name
  }
  if ('const' in schema) return JSON.stringify(schema.const)
  if (schema.enum) return schema.enum.map(value => JSON.stringify(value)).join(' | ')
  if (schema.oneOf || schema.anyOf) return (schema.oneOf ?? schema.anyOf).map(value => `(${render(value, file)})`).join(' | ')
  if (schema.allOf) return schema.allOf.map(value => `(${render(value, file)})`).join(' & ')
  if (Array.isArray(schema.type)) return schema.type.map(type => render({ ...schema, type }, file)).join(' | ')
  if (schema.type === 'array') return `Array<${render(schema.items, file)}>`
  if (schema.type === 'object') {
    const fields = Object.entries(schema.properties ?? {}).map(([name, value]) => `${JSON.stringify(name)}${schema.required?.includes(name) ? '' : '?'}: ${render(value, file)}`)
    if (schema.additionalProperties !== false) fields.push('[key: string]: unknown')
    return `{ ${fields.join('; ')} }`
  }
  const primitive = { string: 'string', integer: 'number', number: 'number', boolean: 'boolean', null: 'null' }[schema.type]
  if (primitive) return primitive
  throw new Error(`不支持的Schema结构：${file} ${JSON.stringify(schema)}`)
}

function generate(version) {
  activeVersion = version
  imports = new Set()
  const lines = []
  for (const [key, name] of registered) {
    const [file, pointer] = key.split('#')
    if (!file.endsWith(`_${version}.json`)) continue
    const schema = pointer ? schemas.get(file).$defs[pointer.split('/').at(-1)] : schemas.get(file)
    lines.push(`export type ${name} = ${render(schema, file)}`)
  }
  const header = `// 自动生成自 contracts/*_${version}.json；请运行 npm run generate:api，勿手工修改。`
  if (imports.size) lines.unshift(`import type { ${[...imports].map(name => `${name} as Legacy${name}`).join(', ')} } from './api'`)
  return `${[header, ...lines].join('\n\n')}\n`
}
const outputArgument = process.argv.indexOf('--output')
const versionArgument = process.argv.indexOf('--version')
const selectedVersion = versionArgument === -1 ? null : process.argv[versionArgument + 1]
if (selectedVersion !== null && !['v1', 'v2'].includes(selectedVersion)) throw new Error('--version只支持v1或v2')
if (outputArgument !== -1) {
  if (!process.argv[outputArgument + 1]) throw new Error('--output需要明确临时文件路径')
  await writeFile(process.argv[outputArgument + 1], generate(selectedVersion ?? 'v1'))
} else {
  for (const version of selectedVersion ? [selectedVersion] : ['v1', 'v2']) {
    const target = new URL(`../src/types/${version === 'v1' ? 'api' : 'api-v2'}.ts`, import.meta.url)
    const output = generate(version)
    if (process.argv.includes('--check')) {
      // Git 的 CRLF 检出不属于契约漂移；真实字段差异仍然失败。
      if ((await readFile(target, 'utf8')).replaceAll('\r\n', '\n') !== output) throw new Error(`API类型与契约漂移（${version}）；运行 npm run generate:api`)
    } else await writeFile(target, output)
  }
}
