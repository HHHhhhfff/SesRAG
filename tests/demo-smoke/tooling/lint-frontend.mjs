import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'

// QLT_007：npm --prefix会改变cwd；固定仓库根，避免全部真实源码落在ESLint基准范围外。
const smokeRoot = fileURLToPath(new URL('../', import.meta.url))
const repositoryRoot = path.resolve(smokeRoot, '../..')
const eslint = new ESLint({ cwd: repositoryRoot, overrideConfigFile: path.join(smokeRoot, 'eslint.config.mjs') })
const results = await eslint.lintFiles(['frontend/src'])
if (!results.length || results.every(item => item.messages.some(message => /ignored/i.test(message.message)))) {
  throw new Error('QLT_007 Lint未检查真实前端源码，不允许空覆盖通过')
}
const formatter = await eslint.loadFormatter('stylish')
console.log(`[Lint] 实际检查${results.length}个前端源码文件；工作目录固定仓库根，保留真实规则。`)
console.log(formatter.format(results))
// 唯一已审阅warning来自已DOMPurify清洗的Markdown渲染；新增warning仍失败，不关规则。
const warnings = results.flatMap(item => item.messages.filter(message => message.severity === 1).map(message => ({ file: path.relative(repositoryRoot, item.filePath).replaceAll('\\','/'), rule: message.ruleId })))
const knownWarnings = warnings.every(row => row.file === 'frontend/src/components/MessageTimeline.vue' && row.rule === 'vue/no-v-html') && warnings.length <= 1
process.exitCode = results.some(item => item.errorCount || item.fatalErrorCount) || !knownWarnings ? 1 : 0
