import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { runCategory, assert, execute, smokeRoot, repoRoot } from '../lib/category-kit.mjs';
import { lazy, isTime } from './run-test-driver.mjs';
import { readJson, artifactFor, runHarness, cleanupNested, baselineResources, assertClean, reportFingerprint, resourceIds, isProcessPresent, inheritedImagesIntact, rejectedRecovery, lifecycleBudget } from './life-runner-driver.mjs';
import { deploymentFaultChecks } from '../tooling/lifecycle-focused.mjs';
import { registeredFrontendProcess } from '../tooling/frontend-resources.mjs';

export const coveredCases = ['LIFE_001', 'LIFE_002', 'LIFE_003', 'LIFE_004', 'LIFE_005', 'LIFE_006', 'LIFE_007', 'LIFE_008', 'LIFE_009'];
await runCategory('life', async s => {
  const registry = [];
  const baseline = lazy(async () => baselineResources());
  const runA = lazy(async () => { await baseline(); return runHarness(s, 'not-ready', { registry }); });
  const runB = lazy(async () => { await baseline(); return runHarness(s, 'not-ready', { category: 'life-unimplemented-a', registry }); });
  const protocol = lazy(() => runHarness(s, 'protocol', { registry }));
  const diagnostic = lazy(() => runHarness(s, 'disabled', { keep: true, registry }));
  const daemonFailure = lazy(() => runHarness(s, 'not-ready', { daemonUnavailable: true, timeoutMs: lifecycleBudget.daemon_seconds*1000, registry }));
  const artifactPath = (record, relative) => path.join(record.artifact, relative);
  const categoryReport = (record, category) => readJson(artifactPath(record, `categories/${category}.json`));
  const categoryState = (record, category) => record.summary.categories.find(item => item.name === category);
  let firstFingerprint;
  try {
    // LIFE_001：运行前记录既有资源，两个新project分别结束后才比较完整隔离及资源清理。
    await s.check('LIFE_001', 'TP-LIFE-001', 'two_fresh_isolated_runs', '同前缀/首选端口两次运行得到不同run/project/owner/卷/网络/tag；仅127.0.0.1发布API/frontend，既有资源不变', async () => {
      const before = await baseline(); const a = await runA(); firstFingerprint = reportFingerprint(a); const b = await runB();
      assert.equal(a.process.code, 3); assert.equal(b.process.code, 3); assertClean(a); assertClean(b);
      assert.notEqual(a.state.run_id, b.state.run_id); assert.notEqual(a.state.compose_project, b.state.compose_project); assert.notEqual(a.state.owner_id, b.state.owner_id);
      assert.ok(a.resources && b.resources, '必须保存两次环境实际资源摘要');
      assert.notDeepEqual(a.resources.networks, b.resources.networks); assert.notDeepEqual(a.resources.volumes, b.resources.volumes); assert.notDeepEqual(a.resources.image_tags, b.resources.image_tags);
      for (const record of [a, b]) {
        assert.equal(record.summary.harness_scenario, 'not-ready');
        for (const service of ['api', 'frontend']) {
          const container = record.resources.containers.find(item => item.service === service); assert.ok(container);
          const bindings = Object.values(container.ports).flat().filter(Boolean); assert.equal(bindings.length, 1); assert.equal(bindings[0].HostIp, '127.0.0.1');
          assert.equal(Number(bindings[0].HostPort), service === 'api' ? record.state.api_port : record.state.frontend_port);
        }
        for (const service of ['postgres', 'redis']) { const container = record.resources.containers.find(item => item.service === service); assert.ok(container); assert.ok(Object.values(container.ports).every(bindings => bindings === null || bindings.length === 0)); }
        assert.ok(record.resources.containers.every(item => item.project === record.state.compose_project));
      }
      assert.deepEqual(baselineResources(), before); inheritedImagesIntact(s); assert.deepEqual(reportFingerprint(a), firstFingerprint);
      return { nested_runs: [a, b].map(record => ({ run_id: record.state.run_id, project: record.state.compose_project, owner_id: record.state.owner_id, api_port: record.state.api_port, frontend_port: record.state.frontend_port, network_ids: record.resources.networks, volume_names: record.resources.volumes, image_tags: record.resources.image_tags, trace: record.trace })), prior_resources_unchanged: true };
    });

    // LIFE_002：门禁正常路径必须看到真实DB探测，daemon故障在新的独立run中检查有界退出。
    await s.check('LIFE_002', 'TP-LIFE-002', 'normal_real_dependency_gates', '真实DB迁移/vector探测、live/ready/Worker/frontend门禁全部满足后才记录分类not_ready', async () => {
      const data = await runA(); assert.equal(data.summary.stages.preflight, 'passed'); assert.equal(data.summary.stages.startup, 'passed');
      const database = fs.readFileSync(artifactPath(data, 'environment/database-probe.txt'), 'utf8').trim().split(/\r?\n/); const head=readJson(artifactPath(data,'environment/database-probe-process.json')).expected_head; assert.deepEqual(database,[head,'vector']);
      const live = readJson(artifactPath(data, 'environment/health-live.json')); const ready = readJson(artifactPath(data, 'environment/health-ready.json'));
      assert.equal(live.status, 'ok'); assert.equal(ready.database, 'ready'); assert.equal(ready.redis, 'ready'); assert.ok(ready.worker_count >= 1);
      assert.ok(data.resources.containers.some(item => item.service === 'frontend')); assert.equal(data.summary.categories.length, 2);
      assert.ok(data.process.duration_ms < 300000); assert.equal(data.cleanup.status, 'passed');
      return { run_id: data.state.run_id, stages: data.summary.stages, real_database_probe: true, health: { live: live.status, database: ready.database, redis: ready.redis, worker_count: ready.worker_count }, duration_ms: data.process.duration_ms, trace: data.trace };
    });
    await s.check('LIFE_002', 'TP-LIFE-002', 'daemon_unavailable', '仅本子进程Docker连接不可达时门禁有界blocked/2，不启动分类/容器，安全报告及本地目录清理完成', async () => {
      const before = baselineResources(); const data = await daemonFailure();
      assert.equal(data.process.code, 2); assert.equal(data.summary.test_status, 'blocked'); assert.equal(data.summary.status, 'blocked');
      assert.notEqual(data.summary.stages.startup, 'passed'); assert.deepEqual(data.summary.categories, []); assert.ok(data.process.duration_ms < 90000);
      assert.ok(data.summary.errors.some(error => error.includes('Docker daemon不可用'))); assert.equal(data.cleanup.status, 'passed');
      assert.ok(!fs.existsSync(path.join(smokeRoot, 'runtime', data.state.run_id))); assert.ok(!fs.existsSync(path.join(smokeRoot, 'tmp', data.state.run_id)));
      assert.deepEqual(baselineResources(), before);
      return { run_id: data.state.run_id, status: data.summary.status, exit_code: data.process.code, duration_ms: data.process.duration_ms, classification_started: false, trace: data.trace };
    });
    await deploymentFaultChecks(s,['compose-config-failure','migration-failure','real-db-probe-failure','redis-cold','redis-strict','worker-readiness-timeout','frontend-readiness-timeout']);

    // LIFE_003：测试自己的not-ready fixture，正式manifest不会被换成伪产品分类。
    for (const selection of ['all', 'subset']) {
      await s.check('LIFE_003', 'TP-LIFE-003', selection, `${selection}未接入分类返回not_ready/3和空checks；清理独立passed；子集不代表全部PRD`, async () => {
        const data = selection === 'all' ? await runA() : await runB(); assert.equal(data.process.code, 3); assert.equal(data.summary.test_status, 'not_ready'); assert.equal(data.summary.status, 'not_ready'); assert.equal(data.summary.cleanup_status, 'passed');
        assert.equal(data.summary.category_selection, selection === 'all' ? 'all' : 'life-unimplemented-a');
        assert.equal(data.summary.categories.length, selection === 'all' ? 2 : 1);
        const manifest = readJson(artifactPath(data, 'manifest.json')); assert.equal(manifest.categories.length, 2); assert.ok(manifest.categories.every(item => item.status === 'not_implemented'));
        for (const item of data.summary.categories) { assert.equal(item.status, 'not_ready'); const report = categoryReport(data, item.name); assert.equal(report.status, 'not_ready'); assert.equal(report.run_id, data.state.run_id); assert.deepEqual(report.checks, []); }
        return { run_id: data.state.run_id, selection: data.summary.category_selection, status: data.summary.status, exit_code: data.process.code, categories: data.summary.categories, trace: data.trace };
      });
    }

    // LIFE_004：一个独立protocol run覆盖每个非法报告，最后缺脚本触发真实finally清理。
    for (const mode of ['valid', 'missing-report', 'empty-passed', 'wrong-run', 'wrong-category', 'nonzero', 'blocked', 'timeout', 'missing-script']) {
      await s.check('LIFE_004', 'TP-LIFE-003', mode, mode === 'valid' ? '六固定参数正确、0退出及合法非空全passed报告，工具分类passed' : `${mode}不满足正式协议时分类/运行不可passed，真实原报告和退出原因保留`, async () => {
        const data = await protocol(); const name = `life-${mode}`;
        assert.equal(data.summary.test_status, 'failed'); assert.equal(data.process.code, 1); assert.equal(data.cleanup.status, 'passed');
        if (mode === 'missing-script') { assert.ok(data.summary.errors.some(error => error.includes('enabled分类缺少脚本'))); assert.ok(!categoryState(data, name) || categoryState(data, name).status !== 'passed'); }
        else {
          const state = categoryState(data, name); assert.ok(state); assert.equal(state.status, mode === 'valid' ? 'passed' : 'failed');
          if (mode === 'missing-report') assert.ok(!fs.existsSync(artifactPath(data, `categories/${name}.json`)));
          if (mode === 'empty-passed') assert.deepEqual(categoryReport(data, name).checks, []);
          if (mode === 'wrong-run') assert.notEqual(categoryReport(data, name).run_id, data.state.run_id);
          if (mode === 'wrong-category') assert.notEqual(categoryReport(data, name).category, name);
          if (mode === 'nonzero') { assert.equal(state.exit_code, 7); assert.equal(categoryReport(data, name).status, 'passed'); }
          if (mode === 'blocked') { assert.equal(categoryReport(data, name).status, 'blocked'); assert.equal(categoryReport(data, name).checks[0].status, 'blocked'); }
          if (mode === 'valid') { assert.equal(state.exit_code, 0); const report = categoryReport(data, name); assert.equal(report.checks.length, 1); assert.ok(report.checks.every(item => item.status === 'passed')); const log = fs.readFileSync(artifactPath(data, `logs/category-${name}.log`), 'utf8'); assert.match(log, /收到六固定参数/); }
          if (mode === 'timeout') {
            assert.equal(state.exit_code, 124); const pids = readJson(artifactPath(data, 'environment/life-timeout-pids.json')); assert.equal(pids.run_id, data.state.run_id);
            assert.ok(!isProcessPresent(pids.parent_pid) && !isProcessPresent(pids.child_pid), '运行器超时未终止自有父子进程树');
          }
        }
        return { run_id: data.state.run_id, scenario: mode, category_state: categoryState(data, name) ?? '缺脚本触发安全失败', overall: data.summary.test_status, trace: data.trace };
      });
    }
    await s.check('LIFE_004', 'TP-LIFE-003', 'disabled_empty_executable_set', '只包含disabled的独立manifest没有可执行检查，test_status必须not_ready且分类skipped，不可passed', async () => {
      const data = await diagnostic(); assert.equal(data.summary.test_status, 'not_ready'); assert.equal(data.summary.categories.length, 1); assert.equal(data.summary.categories[0].status, 'skipped');
      assert.ok(readJson(artifactPath(data, 'manifest.json')).categories.every(item => item.status === 'disabled'));
      return { run_id: data.state.run_id, test_status: data.summary.test_status, categories: data.summary.categories, limitation: '诊断保留总体cleanup_deferred，不能当正式通过', trace: data.trace };
    });

    // LIFE_005：所有报告和证据来自本次nested运行，不引用历史环境报告填结果。
    await s.check('LIFE_005', 'TP-LIFE-004', 'report_identity_evidence_and_redaction', '本次commit/dirty/哈希/UTC/ID/config可追溯，分类/健康/编排/日志/清理证据齐全且无本次随机密码', async () => {
      const git = execute('git', ['rev-parse', 'HEAD'], { timeoutMs: 10000 }); assert.equal(git.code, 0);
      const runnerHash = createHash('sha256').update(fs.readFileSync(path.join(smokeRoot, 'run-demo-smoke.ps1'))).digest('hex').toUpperCase();
      for (const data of [await runA(), await runB()]) {
        assert.equal(data.summary.git_commit, git.stdout.trim()); assert.equal(typeof data.summary.git_dirty, 'boolean'); assert.equal(data.summary.runner_sha256, runnerHash);
        assert.equal(data.summary.run_id, data.state.run_id); assert.equal(data.summary.compose_project, data.state.compose_project); assert.ok(isTime(data.summary.started_at) && isTime(data.summary.finished_at));
        assert.ok(Date.parse(data.summary.finished_at) >= Date.parse(data.summary.started_at)); assert.equal(data.summary.stages.report_collection, 'passed');
        for (const relative of ['summary.json', 'summary.md', 'cleanup.json', 'manifest.json', 'environment/compose-config.txt', 'environment/compose-up.txt', 'environment/compose-ps-before.txt', 'environment/compose-ps-after.txt', 'environment/compose-down.txt', 'environment/health-live.json', 'environment/health-ready.json', 'environment/database-probe.txt', ...['migrate', 'api', 'worker', 'frontend', 'postgres', 'redis'].map(name => `logs/${name}.log`)]) {
          const content = fs.readFileSync(artifactPath(data, relative), 'utf8');
          assert.ok(!data.password || !content.includes(data.password), `证据${relative}泄露本次随机密码`);
        }
        for (const category of data.summary.categories) assert.ok(fs.existsSync(artifactPath(data, `categories/${category.name}.json`)));
        assert.equal(data.summary.cleanup_status, 'passed'); assert.ok(data.cleanup.finished_at);
      }
      return { nested_run_ids: [(await runA()).state.run_id, (await runB()).state.run_id], git_commit: git.stdout.trim(), runner_sha256: runnerHash, report_collection: 'passed', generated_password_absent: true };
    });
    await s.check('LIFE_005', 'TP-LIFE-004', 'historical_artifact_unchanged', '第二次运行不覆盖第一轮summary/md/cleanup/manifest；清理前ps与清理后残留证据分开', async () => {
      const a = await runA(); if (!firstFingerprint) firstFingerprint = reportFingerprint(a); const before = firstFingerprint; const b = await runB();
      assert.deepEqual(reportFingerprint(a), before); assert.notEqual(a.artifact, b.artifact);
      for (const data of [a, b]) { assert.ok(fs.existsSync(artifactPath(data, 'environment/compose-ps-before.txt'))); assert.ok(fs.existsSync(artifactPath(data, 'environment/compose-ps-after.txt'))); assertClean(data); }
      return { preserved_run_id: a.state.run_id, other_run_id: b.state.run_id, historical_sha256: before, cleanup_after_resource_checks: true };
    });

    // LIFE_006：正常、daemon启动失败、分类失败/超时分别验证入口结束后的真实清理。
    for (const sub of ['normal', 'startup_failure', 'category_failure_and_timeout']) {
      await s.check('LIFE_006', 'TP-LIFE-005', sub, `${sub}可捕获路径结束后保留报告、删除本次runtime/tmp并检查自有资源归零`, async () => {
        const data = sub === 'normal' ? await runA() : sub === 'startup_failure' ? await daemonFailure() : await protocol();
        assert.equal(data.cleanup.status, 'passed'); assert.equal(data.summary.cleanup_status, 'passed');
        assert.ok(!fs.existsSync(path.join(smokeRoot, 'runtime', data.state.run_id))); assert.ok(!fs.existsSync(path.join(smokeRoot, 'tmp', data.state.run_id)));
        if (sub !== 'startup_failure') assertClean(data); else { for (const kind of ['containers', 'networks', 'volumes']) assert.deepEqual(resourceIds(kind, data.state.compose_project), []); }
        return { run_id: data.state.run_id, original_exit: data.process.code, cleanup: data.cleanup.status, trace: data.trace };
      });
    }
    await s.check('LIFE_006', 'TP-LIFE-005', 'killed_category_parent_registry_fallback', '分类真实超时kill后没有执行自身恢复，父runner按登记恢复deferred子环境；nested_recovery cleaned=true且两级项目精确零残留', async () => {
      const before = baselineResources();
      const data = await runHarness(s, 'nested-recovery', { registry, timeoutMs: lifecycleBudget.nested_recovery_seconds*1000 });
      assert.equal(data.process.code, 1); assert.equal(data.summary.test_status, 'failed'); assert.equal(data.cleanup.status, 'passed');
      const category = categoryState(data, 'life-nested-deferred'); assert.ok(category); assert.equal(category.status, 'failed'); assert.equal(category.exit_code, 124);
      const marker = readJson(artifactPath(data, 'environment/life-nested-deferred.json'));
      assert.equal(marker.parent_run_id, data.state.run_id); assert.equal(marker.phase, 'deferred_completed'); assert.equal(marker.child_exit_code, 5);
      assert.ok(marker.child_state && marker.resources?.containers.length > 0, '必须有子环境真实deferred后保留资源的证据');
      assert.notEqual(marker.child_state.run_id, data.state.run_id); assert.notEqual(marker.child_state.compose_project, data.state.compose_project);
      const step = data.cleanup.steps.find(item => item.name === 'nested_recovery' && item.run_id === marker.child_state.run_id);
      assert.ok(step, '父runner清理报告缺少登记兜底nested_recovery步骤'); assert.equal(step.project, marker.child_state.compose_project); assert.equal(step.cleaned, true);
      const childArtifact = artifactFor(marker.child_state.run_id); const childCleanup = readJson(path.join(childArtifact, 'cleanup.json'));
      const childRecord = { state: marker.child_state, resources: marker.resources, cleanup: childCleanup, artifact: childArtifact };
      const childClean = assertClean(childRecord); const parentClean = assertClean(data);
      assert.ok(!isProcessPresent(marker.probe_pid), '分类超时后哨兵进程仍存活');
      assert.ok(fs.existsSync(artifactPath(data, `logs/nested-recovery-${marker.child_state.run_id}.log`)));
      assert.deepEqual(baselineResources(), before); inheritedImagesIntact(s);
      return { harness_parent_run_id: data.state.run_id, registered_child_run_id: marker.child_state.run_id, category_timeout_exit: category.exit_code, child_deferred_exit: marker.child_exit_code, parent_fallback: step, child_clean: childClean, parent_clean: parentClean, trace: data.trace, limitation: '证明分类超时后父运行器兜底；仍未模拟父运行器本身硬杀' };
    });
    s.block('LIFE_006','TP-LIFE-005','capturable_interrupt','真实Ctrl+C可捕获中断执行finally','Windows无可用控制台Ctrl+C注入API；Node kill在Windows为终止，不冒充可捕获中断。真实硬杀恢复独立验证。');
    await deploymentFaultChecks(s,['hard-kill-recovery'],'LIFE_006','TP-LIFE-005');
    await s.check('LIFE_006','TP-LIFE-005','browser_sse_client_closure','真实running首片故意异常后所有客户端/服务器/PID观察关闭',async()=>{
      const args=Object.entries(s.ctx.args).flatMap(([k,v])=>['-'+k,v]);
      const result=await registeredFrontendProcess(s.ctx,process.execPath,[path.join(smokeRoot,'tooling/frontend-lifecycle-probe.mjs'),...args],{timeoutMs:lifecycleBudget.client_seconds*1000,env:{PLAYWRIGHT_BROWSERS_PATH:path.join(smokeRoot,'.cache/ms-playwright')}});
      s.ctx.evidence('life/frontend-close-process.json',result);assert.equal(result.code,0);return {exit_code:result.code};
    });

    // LIFE_007：nested项目已经退出且清理完成，主项目仍存活不影响其精确残留核对。
    await s.check('LIFE_007', 'TP-LIFE-006', 'zero_exact_residuals_and_preserved_cache', '两个完成nested run的容器/网络/卷/匿名卷/tag/runtime/tmp精确归零；报告、主源镜像和共享缓存有意保留', async () => {
      const a = await runA(); const b = await runB(); const clean = [assertClean(a), assertClean(b)];
      inheritedImagesIntact(s); assert.ok(fs.existsSync(path.join(smokeRoot, 'node_modules')));
      assert.ok(fs.existsSync(path.join(smokeRoot, '.cache', 'ms-playwright')));
      assert.ok(resourceIds('containers', s.ctx.context.compose_project).length > 0, '主project不应被nested清理误删');
      return { nested_cleanup: clean, main_project_preserved: s.ctx.context.compose_project, reports_and_shared_tool_cache_preserved: true };
    });

    // LIFE_008：真实KeepContainers/5后立刻恢复；清理失败4只给生产状态函数局部证据。
    await s.check('LIFE_008', 'TP-LIFE-006', 'diagnostic_deferred_then_recovery', 'KeepContainers真实cleanup_deferred/5且runtime/资源保留，CleanupRunId保存旧summary并精确清至零残留', async () => {
      const data = await diagnostic(); assert.equal(data.process.code, 5); assert.equal(data.summary.status, 'cleanup_deferred'); assert.equal(data.summary.cleanup_status, 'deferred');
      assert.ok(fs.existsSync(path.join(smokeRoot, 'runtime', data.state.run_id))); assert.ok(fs.existsSync(path.join(smokeRoot, 'tmp', data.state.run_id))); assert.ok(resourceIds('containers', data.state.compose_project).length > 0);
      const old = data.summary; await cleanupNested(s, data); assert.ok(data.recovery); assert.equal(data.recovery.process.code, 3); assert.equal(data.recovery.cleanup.status, 'passed'); assertClean(data, data.recovery.cleanup);
      const backups = fs.readdirSync(data.artifact).filter(name => /^summary-before-cleanup-.*\.json$/.test(name)); assert.ok(backups.length > 0);
      assert.ok(backups.some(name => JSON.stringify(readJson(artifactPath(data, name))) === JSON.stringify(old)), '恢复清理前必须另存诊断原报告');
      inheritedImagesIntact(s);
      return { run_id: data.state.run_id, original_status: old.status, original_exit: data.process.code, recovery_exit: data.recovery.process.code, recovered_cleanup: data.recovery.cleanup.status, original_summary_preserved: true };
    });
    await s.check('LIFE_008', 'TP-LIFE-006', 'cleanup_failure_status_precedence_function', '真实Get-SmokeOutcome对passed/failed/not_ready均以cleanup_failed/4优先，只证明状态函数局部行为', async () => {
      // Node按UTF-8读取管道；Windows PowerShell子进程必须显式输出UTF-8，防止中文证据乱码误判。
      const script = `[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); $OutputEncoding=[Console]::OutputEncoding; . '${path.join(smokeRoot, 'lib', 'smoke-common.ps1').replaceAll("'", "''")}'; foreach($testState in @('passed','failed','not_ready')) { $v=Get-SmokeOutcome $testState 'failed'; if($v.status -ne 'cleanup_failed' -or $v.exit_code -ne 4) { throw 'LIFE_008 清理失败未优先' } }; Write-Output 'LIFE_008 cleanup_failed/4状态函数通过'`;
      const result = execute('pwsh', ['-NoProfile', '-Command', script], { timeoutMs: 15000 }); assert.equal(result.code, 0); assert.match(result.stdout, /状态函数通过/);
      return { function: 'Get-SmokeOutcome', tested_product_statuses: ['passed', 'failed', 'not_ready'], expected_cleanup_status: 'cleanup_failed', exit_code: 4, limitation: '未制造真实down或文件删除失败' };
    });
    await deploymentFaultChecks(s,['cleanup-failure','cleanup-share-read'],'LIFE_008','TP-LIFE-006');

    // LIFE_009：调用生产路径函数动态拒绝危险/链接目录；忽略边界用真实git检查。
    await s.check('LIFE_009', 'TP-LIFE-007', 'production_path_rejections', '合法精确子目录可删除，根/绝对/逃逸/链接根及链接子项拒绝且链接目标保留', async () => {
      const sandboxRoot = path.dirname(s.ctx.args.FixtureDir);
      const result = execute('pwsh', ['-NoProfile', '-File', path.join(smokeRoot, 'specific_test_script', 'life-path-driver.ps1'), '-SandboxRoot', sandboxRoot], { timeoutMs: 30000 });
      assert.equal(result.code, 0, 'LIFE_009 路径驱动未正常结束'); const line = result.stdout.split(/\r?\n/).find(item => item.startsWith('SMOKE_JSON:')); assert.ok(line);
      const data = JSON.parse(line.slice('SMOKE_JSON:'.length)); assert.equal(data.checks.length, 11); assert.ok(data.checks.every(item => item.passed));
      return { checks: data.checks, actual_production_functions: ['Get-SmokeChildPath', 'Remove-SmokeChild'], exact_tmp_sandbox_removed: true };
    });
    await s.check('LIFE_009', 'TP-LIFE-007', 'git_and_build_context_exclusions', 'runtime/artifacts/tmp/cache/node_modules及本地配置实际被git忽略且构建上下文规则排除', async () => {
      const excluded = ['runtime/sentinel', 'artifacts/sentinel', 'tmp/sentinel', '.cache/sentinel', 'node_modules/sentinel', 'compose/.env.demo-smoke.local'];
      for (const name of excluded) {
        const relative = `tests/demo-smoke/${name}`; const result = execute('git', ['check-ignore', relative], { timeoutMs: 10000 }); assert.equal(result.code, 0, `Git未忽略${relative}`);
      }
      const dockerignore = fs.readFileSync(path.join(repoRoot, '.dockerignore'), 'utf8').split(/\r?\n/).map(line => line.trim());
      for (const entry of ['tests/demo-smoke/runtime', 'tests/demo-smoke/artifacts', 'tests/demo-smoke/tmp', 'tests/demo-smoke/.cache', 'tests/demo-smoke/node_modules', 'tests/demo-smoke/compose/.env.demo-smoke.local']) assert.ok(dockerignore.includes(entry), `Docker上下文未排除${entry}`);
      return { ignored_paths: excluded, actual_git_check_ignore: true, build_context_rules_present: true };
    });
    await s.check('LIFE_009', 'TP-LIFE-007', 'mismatched_saved_project_recovery', '误project/marker恢复凭据在任何Docker销毁前拒绝，不影响开发资源，仅删除刚创建的无部署本次目录', async () => {
      const before = baselineResources(); const data = await rejectedRecovery(s);
      assert.equal(data.process.code, 2); assert.equal(data.summary.status, 'blocked'); assert.equal(data.summary.stages.startup, 'not_run');
      assert.ok(data.summary.errors.some(error => error.includes('恢复清理凭据校验失败'))); assert.deepEqual(data.summary.categories, []);
      assert.deepEqual(baselineResources(), before); inheritedImagesIntact(s);
      return { invalid_run_id: data.run_id, rejected_before_deployment: true, exit_code: data.process.code, prior_resources_unchanged: true };
    });
    await s.check('LIFE_009', 'TP-LIFE-007', 'category_has_no_destroy_permission', '分类共享Context对down/rm/prune在调用Docker前拒绝，生命周期销毁仅归总入口', async () => {
      for (const command of ['down', 'rm', 'prune']) assert.throws(() => s.ctx.compose([command]), /分类无环境销毁权限/);
      return { denied_before_docker_execution: ['down', 'rm', 'prune'], lifecycle_owner: 'run-demo-smoke.ps1' };
    });
  } finally {
    // LIFE_006/008：无论断言失败，记录过且非主run的nested runtime都交正式入口精确恢复。
    for (const record of registry) {
      if (record.state && [record.state.run_id,record.state.run_id+'-recovery.json'].some(name=>fs.existsSync(path.join(smokeRoot, 'runtime', name)))) {
        await s.check('LIFE_006', 'TP-LIFE-005', `finally_recovery_${record.state.run_id}`, '分类finally恢复尚存的自有nested run，仅CleanupRunId且残留精确归零', async () => { await cleanupNested(s, record); assertClean(record, record.recovery?.cleanup ?? record.cleanup); return { run_id: record.state.run_id, recovered_in_finally: true }; });
      }
    }
  }
});
