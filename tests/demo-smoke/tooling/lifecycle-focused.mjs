import fs from 'node:fs'
import path from 'node:path'
import { Context, Suite, parseArgs, assert, smokeRoot } from '../lib/category-kit.mjs'
import { runHarness, cleanupNested, assertClean, readJson, restoreLockTestMissingFiles } from '../specific_test_script/life-runner-driver.mjs'

// 有界固定场景专项；独立ArtifactDir，真实主入口仍是唯一创建/销毁者。
export async function deploymentFaultChecks(s, selected, caseId = 'LIFE_002', tp = 'TP-LIFE-002') {
  const registry = []
  try {
    for (const scenario of selected) await s.check(caseId, tp, scenario, '真实故障阶段/退出码/未运行分类准确，精确清理或保留可恢复凭据', async () => {
      const data = await runHarness(s, scenario, { registry })
      if (scenario === 'hard-kill-recovery') {
        assert.ok(data.hard_kill_armed); assert.equal(data.summary.status, 'hard_killed')
        await cleanupNested(s, data); assert.equal(data.recovery.process.code, 3); assertClean(data, data.recovery.cleanup)
        const recovered = readJson(path.join(data.artifact, 'environment/registered-cleanup.json'))
        assert.equal(recovered.status, 'passed'); assert.deepEqual(recovered.errors, [])
        assert.ok(recovered.observations.some(row => row.container && row.absent))
      } else if (['cleanup-failure','cleanup-share-read'].includes(scenario)) {
        assert.equal(data.process.code, 4); assert.equal(data.cleanup.status, 'failed')
        assert.ok(fs.existsSync(path.join(smokeRoot, 'runtime', data.state.run_id)))
        assert.ok(data.cleanup.steps.some(row => row.name === 'cleanup_exception'))
        const runtime=path.join(smokeRoot,'runtime',data.state.run_id)
        for(const [name,bytes] of Object.entries(data.recovery_backup))assert.deepEqual(fs.readFileSync(path.join(runtime,name)),bytes,'清理失败必须保留完整恢复材料')
        const capsule=readJson(runtime+'-recovery.json')
        assert.equal(capsule.run_id,data.state.run_id);assert.equal(capsule.project,data.state.compose_project)
        for(const name of ['context.json','compose.env','resources.json'])assert.ok(capsule.files[name],'恢复胶囊必须保留完整凭据/资源身份')
        s.ctx.evidence(`life/capsule-${data.state.run_id}.json`,{run_id:data.state.run_id,project:data.state.compose_project,names:Object.keys(capsule.files),credentials_preserved:true})
        await cleanupNested(s, data); assert.equal(data.recovery.process.code, 3); assertClean(data, data.recovery.cleanup)
      } else {
        assertClean(data)
        if (scenario === 'redis-cold') {
          assert.equal(data.summary.stages.startup, 'passed')
          const ready = readJson(path.join(data.artifact, 'environment/health-ready.json'))
          assert.equal(ready.redis, 'degraded'); assert.equal(ready.database, 'ready'); assert.equal(ready.worker, 'unknown'); assert.equal(ready.worker_count, 0)
          assert.equal(readJson(path.join(data.artifact, 'environment/redis-cold-run.json')).status, 'succeeded')
        } else {
          assert.ok([1, 2].includes(data.process.code)); assert.deepEqual(data.summary.categories, [])
          assert.equal(data.summary.stages.tests, 'not_run')
          assert.equal(data.summary.stages[scenario === 'compose-config-failure' ? 'preflight' : 'startup'], 'failed')
          if (scenario === 'migration-failure') {
            const rows = fs.readFileSync(path.join(data.artifact, 'environment/compose-ps-before.txt'), 'utf8').trim().split(/\r?\n/).filter(x => x.startsWith('{')).map(JSON.parse)
            assert.equal(rows.find(x => x.Service === 'migrate').ExitCode, 42)
            for (const name of ['api', 'worker']) assert.ok(rows.find(x => x.Service === name)?.State !== 'running')
          }
          if (scenario === 'real-db-probe-failure') assert.notEqual(readJson(path.join(data.artifact, 'environment/database-probe-process.json')).exit_code, 0)
        }
      }
      return { run_id: data.state.run_id, child_exit: data.process.code, summary_exit: data.summary.exit_code, stages: data.summary.stages, trace: data.trace }
    })
  } finally {
    for (const row of registry) if ([row.state.run_id,row.state.run_id+'-recovery.json'].some(name=>fs.existsSync(path.join(smokeRoot, 'runtime',name)))) { restoreLockTestMissingFiles(s,row); await cleanupNested(s, row) }
  }
}

if (process.argv[1]?.endsWith('lifecycle-focused.mjs')) {
  const ctx = new Context(parseArgs()), s = new Suite('life', ctx)
  const scenarios = (process.env.SMOKE_LIFECYCLE_SCENARIOS || 'compose-config-failure,migration-failure,redis-cold,real-db-probe-failure,worker-readiness-timeout,frontend-readiness-timeout,cleanup-failure').split(',')
  await deploymentFaultChecks(s, scenarios)
  const result = s.finish()
  process.exitCode = result.status === 'passed' ? 0 : 1
}
