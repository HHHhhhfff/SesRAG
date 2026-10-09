import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import Ajv from 'ajv/dist/2020.js'
import addFormats from 'ajv-formats'
import { ESLint } from 'eslint'

// 任务1的依赖能力自检：仅用哨兵HTML/语法/组件，不计入产品manifest。
const root = fileURLToPath(new URL('../', import.meta.url))
const repo = path.resolve(root, '../..')
const [major, minor] = process.versions.node.split('.').map(Number)
assert(major >= 26 || (major === 24 && minor >= 15), '测试工具需Node24.15+的24.x或26+，Node25不在依赖支持范围')
process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(root, '.cache/ms-playwright')
// Playwright在模块初始化时读取目录，必须先配置再动态导入。
const { chromium } = await import('playwright')
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  await page.setContent('<h1>工具就绪</h1>')
  assert.equal(await page.locator('h1').textContent(), '工具就绪')
  console.log(`[工具通过] Chromium ${browser.version()}启动、中文DOM读取和关闭`)
} finally {
  await browser.close()
}

const ajv = new Ajv({ strict: false, allErrors: true })
addFormats(ajv)
for (const url of [new URL('../specific_test_script/category-result.schema.json', import.meta.url),
  new URL('../../../contracts/run_event_v1.json', import.meta.url)]) {
  ajv.compile(JSON.parse(await readFile(url, 'utf8')))
}
const validate = ajv.compile({ type: 'object', required: ['id'] })
assert(validate({ id: '工具哨兵' }))
assert(!validate({}))
console.log('[工具通过] Ajv可编译正式Schema、接受合法哨兵并拒绝缺字段')

const eslint = new ESLint({ cwd: repo, overrideConfigFile: path.join(root, 'eslint.config.mjs') })
const good = await eslint.lintText('export const value: number = 1\n', {
  filePath: path.join(repo, 'frontend/src/tool-probe.ts'),
})
assert.equal(good[0].errorCount, 0, JSON.stringify(good[0].messages))
const bad = await eslint.lintText('export const value: = 1\n', {
  filePath: path.join(repo, 'frontend/src/tool-probe.ts'),
})
assert(bad[0].errorCount > 0, 'ESLint必须真的检查TS，而不是忽略所有文件')
const sfc = await eslint.lintText('<script setup lang="ts">const name: string = "工具"</script><template><h1>{{ name }}</h1></template>', {
  filePath: path.join(repo, 'frontend/src/ToolProbe.vue'),
})
assert.equal(sfc[0].fatalErrorCount, 0, JSON.stringify(sfc[0].messages))
assert(!sfc[0].messages.some(item => item.message.includes('ignored')), 'Vue探针不能被忽略')
const browserTypes = await eslint.lintText('<script setup lang="ts">function read(event: Event) { return event.target as HTMLInputElement }</script><template><button @click="read">类型探针</button></template>', {
  filePath: path.join(repo, 'frontend/src/BrowserTypesProbe.vue'),
})
assert.equal(browserTypes[0].errorCount, 0, JSON.stringify(browserTypes[0].messages))
console.log('[工具通过] 独立ESLint正确解析TS/Vue并拒绝非法语法（未Lint产品）')

const probe = spawnSync(process.execPath, [path.join(root, 'node_modules/vitest/vitest.mjs'),
  'run', '--config', path.join(root, 'tooling/vitest-tools.config.mjs')], {
  cwd: root, encoding: 'utf8', timeout: 60000, windowsHide: true,
})
if (probe.stdout) console.log(probe.stdout)
if (probe.stderr) console.error(probe.stderr)
assert.equal(probe.status, 0, `Vitest工具探针失败：${probe.error?.message ?? probe.status}`)
console.log('Node工具自检完成；产品unit:frontend无用例时仍非零，不把探针当产品通过。')
