import fs from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { assert, smokeRoot } from '../lib/category-kit.mjs'
import { allComponentChecks } from '../specific_test_script/fe-component-checks.mjs'
import { registeredFrontendProcess } from './frontend-resources.mjs'

// FE组件结果36项逐个按精确标题消费；原始JSON和进程输出同时保留。
export async function runFrontendComponents(s) {
  const rawPath = path.join(s.ctx.args.RuntimeDir, `fe-vitest-${randomUUID()}.json`)
  const result = await registeredFrontendProcess(s.ctx, process.execPath, [path.join(smokeRoot, 'node_modules/vitest/vitest.mjs'), 'run', '--config', path.join(smokeRoot, 'vitest.config.mjs'), 'specific_test_script/fe-workspace.test.ts', '--reporter=json', `--outputFile=${rawPath}`], { timeoutMs: 60000, kind: 'vitest-process-tree' })
  const raw = fs.existsSync(rawPath) ? JSON.parse(fs.readFileSync(rawPath, 'utf8')) : null
  const evidence = s.ctx.evidence('fe/components-36.json', { process: result, result: raw })
  const assertions = raw?.testResults?.flatMap(item => item.assertionResults ?? []) ?? []
  for (const [id, tp, sub, expected, title] of allComponentChecks) await s.check(id, tp, sub, expected, async () => {
    assert.equal(assertions.length, 36, '必须收集完整36项，新增/遗漏须显式更新映射')
    const matches = assertions.filter(item => item.title === title)
    assert.equal(matches.length, 1, `未唯一收集断言：${title}`)
    assert.equal(matches[0].status, 'passed', '真实组件断言失败，见完整Vitest证据')
    assert.equal(result.code, 0, '组件进程存在未收集错误')
    return { vitest_title: title, status: matches[0].status, evidence, duration_ms: matches[0].duration }
  })
}
