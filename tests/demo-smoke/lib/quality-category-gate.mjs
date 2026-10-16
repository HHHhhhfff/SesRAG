import fs from 'node:fs'
import path from 'node:path'
import {createHash} from 'node:crypto'
import { assert, smokeRoot, safeChild, readCases, repoRoot } from './category-kit.mjs'
import { requireCategoryChecks } from './category-report-contract.mjs'
import { registeredFrontendProcess } from '../tooling/frontend-resources.mjs'

// 缺报告只运行本run正式完整分类；从不搜索历史/专项拼接报告。
export async function categoryGate(ctx, category, expectedIds) {
  const manifest = JSON.parse(fs.readFileSync(path.join(smokeRoot, 'specific_test_script/manifest.json')))
  const entry = manifest.categories.find(row => row.name === category)
  assert.ok(entry?.status === 'enabled')
  const reportPath = path.join(ctx.args.ArtifactDir, 'categories', category + '.json')
  if (!fs.existsSync(reportPath)) {
    const args = Object.entries(ctx.args).flatMap(([key, value]) => ['-' + key, value])
    const sourceHashes={}
    const scan=folder=>{
      for(const entry of fs.readdirSync(folder,{withFileTypes:true})){
        if(['node_modules','.cache','artifacts','runtime','tmp','__pycache__'].includes(entry.name))continue
        const target=path.join(folder,entry.name)
        if(entry.isDirectory())scan(target)
        else if(/\.(py|mjs|ps1|ts|vue|json)$/.test(entry.name))sourceHashes[path.relative(repoRoot,target).replaceAll('\\','/')]=createHash('sha256').update(fs.readFileSync(target)).digest('hex')
      }
    }
    for(const folder of ['backend','migrations','contracts','frontend/src','frontend/scripts','tests/demo-smoke'])scan(path.join(repoRoot,folder))
    const startedAt=new Date().toISOString()
    ctx.evidence(`qlt/standalone-${category}-sources.json`,{started_at:startedAt,source_sha256:sourceHashes})
    const result = await registeredFrontendProcess(ctx, process.execPath, [path.join(smokeRoot, 'specific_test_script', entry.script), ...args], {
      kind: 'quality-category', timeoutMs: entry.timeout_seconds * 1000,
      env: { PLAYWRIGHT_BROWSERS_PATH: path.join(smokeRoot, '.cache/ms-playwright') },
    })
    ctx.evidence(`qlt/standalone-${category}.log`, result.stdout + result.stderr)
    ctx.evidence(`qlt/standalone-${category}-process.json`, { started_at:startedAt,finished_at:new Date().toISOString(),command:[process.execPath,entry.script,...args],exit_code: result.code, timed_out: result.timed_out, launch_error: result.error ?? null })
    assert.ok(!result.error && !result.timed_out && [0, 1, 2].includes(result.code), '分类未完整结束')
  }
  const report = JSON.parse(fs.readFileSync(reportPath))
  const selected = requireCategoryChecks(report, ctx.args.RunId, category, expectedIds)
  const deferred = new Set(['PAR_004__TP-PAR-008__full-region-support','FE_009__TP-FE-010__ordinary-browser-offline'])
  assert.ok(report.checks.every(row => row.status === 'passed' || (row.status==='blocked'&&deferred.has(row.id))), '完整分类包含failed或未约定未完成检查，不能以专项通过掩盖')
  // 编号真源独立于脚本声明（WK用Array.from生成声明，不能用文本正则漏掉）。
  for (const [id,item] of readCases()) if (id.startsWith(category.toUpperCase()+'_')) {
    for(const tp of item.points)assert.ok(report.checks.some(row => row.id.startsWith(id+'__'+tp+'__')), '缺少完整分类用例/测试点：'+id+'/'+tp)
  }
  for (const check of report.checks) for (const evidence of check.evidence) assert.ok(fs.existsSync(safeChild(ctx.args.ArtifactDir, evidence)), '证据不存在：' + evidence)
  return { category, checks: report.checks.length, required_passed: selected.length, status: report.status, report: `categories/${category}.json` }
}
