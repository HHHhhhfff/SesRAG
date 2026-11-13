import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import Ajv2020 from 'ajv/dist/2020.js'
import addFormats from 'ajv-formats'
import standaloneCode from 'ajv/dist/standalone/index.js'
import { build } from 'esbuild'

const schema = JSON.parse(await readFile(new URL('../../contracts/run_event_v3.json', import.meta.url), 'utf8'))
const hash = createHash('sha256').update(JSON.stringify(schema)).digest('hex')
const eventKinds = [...new Set(schema.anyOf.map(branch => {
  const kind = schema.$defs[branch.$ref?.replace('#/$defs/', '')]?.properties?.type?.const
  if (typeof kind !== 'string') throw new Error('RunEvent分支缺少事件类型常量')
  return kind
}))]
// 完整编译正式联合契约；不进行类型强转、默认值补齐或未知字段删除。
const ajv = new Ajv2020({ strict: true, inlineRefs: false, code: { source: true }, validateFormats: true })
addFormats(ajv)
const validate = ajv.compile(schema)
// standalone的CommonJS运行时引用统一打包为浏览器ESM；运行时不需要eval或远程Schema。
const result = await build({
  stdin: { contents: standaloneCode(ajv, validate), resolveDir: fileURLToPath(new URL('../', import.meta.url)), sourcefile: 'run-event-validator.cjs', loader: 'js' },
  bundle: true, format: 'esm', platform: 'browser', target: 'es2022', minify: true,
  write: false, legalComments: 'none', logLevel: 'silent',
})
const header = `// 自动生成自 contracts/run_event_v3.json；运行 npm run generate:events，勿手改。\n// Schema SHA-256: ${hash}\n`
const outputs = {
  'run-event-validator.js': header + result.outputFiles[0].text + `export const eventKinds = ${JSON.stringify(eventKinds)}\n`,
  'run-event-validator.d.ts': header + "import type { RunEvent } from '../../types/api-v3'\ndeclare const validate: (value: unknown) => value is RunEvent\nexport default validate\nexport declare const eventKinds: ReadonlyArray<RunEvent['type']>\n",
}
const directory = new URL('../src/events/generated/', import.meta.url)
if (!process.argv.includes('--check')) await mkdir(directory, { recursive: true })
for (const [name, output] of Object.entries(outputs)) {
  const target = new URL(name, directory)
  if (process.argv.includes('--check')) {
    const actual = await readFile(target, 'utf8').catch(() => '')
    if (actual.replaceAll('\r\n', '\n') !== output) throw new Error(`Event校验器与契约漂移（${name}）；运行 npm run generate:events`)
  } else await writeFile(target, output)
}
