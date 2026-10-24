import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { openCategory, helper, repoRoot } from '../tooling/product-category.mjs';
import { runCommand } from '../tooling/process-registry.mjs';
import { assert, thread, send, done, scenario, barrier, release, observations, request } from './support.mjs';

async function main(contextFile) {
  const suite = openCategory('quality', contextFile); const c = suite.context;
  // QLT_001：场景驱动真实产品请求；Provider自测只作协议辅助，不替代产品结算。
  await suite.test('QLT_001', async () => {
    const results = [];
    for (const kind of ['normal', 'slow', 'stall', 'empty', 'malformed', 'disconnect', 'context-limit', 'http-error']) {
      await scenario(c, { kind, chunks: ['HISTORY-QUALITY-INPUT', '完成'], ...(kind === 'http-error' ? { http_status: 401 } : {}) });
      const t = await thread(c, `QLT_001-${kind}`); const created = await send(c, t, 'HISTORY-QUALITY-INPUT', 'ws-http-a');
      if (kind === 'stall') { const held = await barrier(c); assert.ok(held.request_seq); await release(c, held); }
      const finished = await done(c, created.run_id, 90000);
      if (['normal', 'slow', 'stall'].includes(kind)) assert.equal(finished.status, 'succeeded'); else assert.equal(finished.status, 'failed');
      const observed = await observations(c); assert.equal(observed.truncated, false); assert.ok(observed.requests.length > 0);
      const serialized = JSON.stringify(observed); assert.ok(!serialized.includes(process.env.MODEL_API_KEY)); assert.ok(!serialized.includes(process.env.PROVIDER_CONTROL_TOKEN));
      results.push({ kind, run_id: created.run_id, status: finished.status, error_code: finished.last_error_code, observation_count: observed.requests.length });
    }
    return { actual: '8种场景均通过正式API/Worker实际调用并核对终态；stall屏障定向释放，安全实收观测未截断或泄露凭据。', results };
  });
  let backendError;
  try { await helper(c, 'run-quality-probe'); } catch (error) { backendError = error.message; }
  const backendFile = path.join(suite.tmp, 'quality-backend.json');
  const backend = fs.existsSync(backendFile) ? JSON.parse(fs.readFileSync(backendFile, 'utf8')) : { checks: [] };
  if (backendError) backend.checks.push({ name: 'probe-engineering', exit_code: 2, reason: backendError });
  const backendEvidence = [];
  for (const name of ['quality-backend.json', 'ruff.log', 'mypy.log', 'pytest.log', 'counter.log', 'quality-pytest.xml', 'counter-pytest.xml']) {
    const target = path.join(suite.tmp, name); backendEvidence.push(suite.evidence(name, fs.existsSync(target) ? fs.readFileSync(target, 'utf8') : { status: 'not_run', reason: '探针未产生该项证据', backend_error: backendError }));
  }
  // QLT_002：每项质量命令独立保留，不允许pytest通过掩盖Ruff/mypy失败。
  await suite.test('QLT_002', async () => {
    const checks = backend.checks.filter((item) => item.name !== 'counter');
    const required = ['ruff', 'mypy', 'pytest', 'bad-contract-rejected'];
    return { status: required.every((name) => checks.some((item) => item.name === name && item.exit_code === 0)) && checks.every((item) => item.exit_code === 0) ? 'passed' : 'failed', actual: checks.map((item) => `${item.name}退出${item.exit_code}`).join('；') || '后端探针无完整结果', checks,
      reason_code: 'BACKEND_QUALITY_GATE', reason: '后端质量门禁存在非零结果，详见各命令日志。', evidence_paths: backendEvidence };
  });
  // QLT_003：运行当前源码真实工具；负例仅写本轮tmp，不修改冻结源码。
  await suite.test('QLT_003', async () => {
    const front = path.join(repoRoot, 'frontend'); const checks = [];
    const commands = [
      ['check:api', ['scripts/generate-api-types.mjs', '--check']],
      ['typecheck', ['node_modules/vue-tsc/bin/vue-tsc.js', '--noEmit']],
      ['lint', ['node_modules/eslint/bin/eslint.js', 'src', 'scripts', 'tests', 'vite.config.ts', 'vitest.config.ts', 'eslint.config.mjs']],
      ['test:unit', ['node_modules/vitest/vitest.mjs', 'run']],
      ['build:types', ['node_modules/vue-tsc/bin/vue-tsc.js', '-b']],
      ['build:vite', ['node_modules/vite/bin/vite.js', 'build']],
    ];
    const evidence = [];
    for (const [name, args] of commands) {
      const result = await runCommand(process.execPath, args, { cwd: front, timeoutMs: 180000 });
      checks.push({ name, exit_code: result.code, timed_out: result.timedOut, truncated: result.truncated });
      evidence.push(suite.evidence(`frontend-${name.replace(':', '-')}.log`, result.output));
    }
    const invalidType = path.join(suite.tmp, 'negative-type.ts'); fs.writeFileSync(invalidType, 'const value: number = "synthetic-invalid-type";\nexport { value };\n');
    const typeNegative = await runCommand(process.execPath, [path.join(front, 'node_modules/typescript/bin/tsc'), '--strict', '--noEmit', '--skipLibCheck', invalidType], { cwd: suite.tmp, timeoutMs: 60000 });
    checks.push({ name: 'negative-type-rejected', exit_code: typeNegative.code !== 0 && /TS2322/.test(typeNegative.output) ? 0 : 1 }); evidence.push(suite.evidence('negative-type.log', typeNegative.output));
    const invalidLint = path.join(suite.tmp, 'negative-lint.mjs'); fs.writeFileSync(invalidLint, 'const value = ;\n');
    const lintNegative = await runCommand(process.execPath, [path.join(front, 'node_modules/eslint/bin/eslint.js'), '--no-config-lookup', invalidLint], { cwd: suite.tmp, timeoutMs: 60000 });
    checks.push({ name: 'negative-lint-rejected', exit_code: lintNegative.code !== 0 && /Parsing error/.test(lintNegative.output) ? 0 : 1 }); evidence.push(suite.evidence('negative-lint.log', lintNegative.output));
    const invalidTest = path.join(suite.tmp, 'negative-component.test.mjs'); const config = path.join(suite.tmp, 'vitest-negative.config.mjs');
    fs.writeFileSync(invalidTest, `import {test,expect} from ${JSON.stringify(pathToFileURL(path.join(front, 'node_modules/vitest/dist/index.js')).href)}; test('synthetic-component-failure',()=>expect(1).toBe(2));\n`);
    fs.writeFileSync(config, `export default {test:{include:['negative-component.test.mjs'],environment:'node'}};\n`);
    const componentNegative = await runCommand(process.execPath, [path.join(front, 'node_modules/vitest/vitest.mjs'), 'run', '--config', config], { cwd: suite.tmp, timeoutMs: 60000 });
    checks.push({ name: 'negative-component-rejected', exit_code: componentNegative.code !== 0 && /synthetic-component-failure/.test(componentNegative.output) ? 0 : 1 }); evidence.push(suite.evidence('negative-component.log', componentNegative.output));
    return { status: checks.every((item) => item.exit_code === 0 && !item.timed_out && !item.truncated) ? 'passed' : 'failed', actual: checks.map((item) => `${item.name}退出${item.exit_code}`).join('；'), checks,
      reason_code: 'FRONTEND_QUALITY_GATE', reason: '前端质量命令或对应负例未满足门禁；不是缺命令当通过。', evidence_paths: evidence };
  });
  // QLT_004：固定版本及缺损/禁止联网负例在独立工具进程执行。
  await suite.test('QLT_004', async () => {
    const check = backend.checks.find((item) => item.name === 'counter');
    return { status: check?.exit_code === 0 ? 'passed' : 'failed', actual: `离线TokenCounter/上下文固定节点退出${check?.exit_code ?? '未执行'}；缺失/损坏缓存负例包含禁止网络访问断言。`, reason_code: 'COUNTER_REGRESSION', reason: '计数器回归失败或未执行，见日志。', evidence_paths: backendEvidence };
  });
  // QLT_005：分类阶段仅记录准备；最终判定由总入口清理完成后补写。
  await suite.test('QLT_005', async () => {
    const health = (await request(c, '/health/ready')).data; assert.equal(health.database, 'ready'); assert.ok(health.worker_count >= 1);
    const failure = await helper(c, 'expected-tool-failure'); assert.equal(failure.result.expected_exit_observed, true);
    return { status: 'blocked', actual: '正式部署依赖/Worker真实就绪，受控one-off非零失败已被正确识别；等待总入口finally清理和独立残留审计后才能完成闭环判定。', reason_code: 'AWAITING_OUTER_CLEANUP', reason: '分类进程仍在容器存活阶段，禁止提前自证清理成功。', health, expected_failure: true };
  });
  // QLT_006：镜像所有层、前端产物和Git跟踪输入使用同一轮虚假Secret检查。
  await suite.test('QLT_006', async () => {
    await helper(c, 'scan-secret-images'); const scan = JSON.parse(fs.readFileSync(path.join(suite.tmp, 'secret-image-scan.json'), 'utf8'));
    const evidence = suite.evidence('secret-image-scan.json', scan); assert.equal(scan.status, 'passed'); assert.ok(scan.members_scanned > 0);
    const listed = await runCommand('git', ['ls-files', '-z'], { cwd: repoRoot }); assert.equal(listed.code, 0);
    const needles = [process.env.MODEL_API_KEY, process.env.PROVIDER_CONTROL_TOKEN].filter(Boolean); const hits = []; let files = 0;
    for (const relative of listed.stdout.split('\0').filter(Boolean)) {
      const absolute = path.join(repoRoot, relative); if (!fs.existsSync(absolute) || !fs.lstatSync(absolute).isFile()) continue;
      const data = fs.readFileSync(absolute); files++; if (needles.some((value) => data.includes(Buffer.from(value)))) hits.push(relative);
    }
    const dist = path.join(repoRoot, 'frontend/dist');
    function walk(directory) { for (const item of fs.readdirSync(directory, { withFileTypes: true })) { const file = path.join(directory, item.name); if (item.isDirectory()) walk(file); else if (needles.some((value) => fs.readFileSync(file).includes(Buffer.from(value)))) hits.push(path.relative(repoRoot, file)); } }
    assert.ok(fs.existsSync(dist), '前端构建产物缺失，不能声称已扫描'); walk(dist); assert.deepEqual(hits, []);
    const reportAudit = await helper(c, 'audit-artifact-secrets'); assert.equal(reportAudit.result.files_with_secret, 0);
    return { actual: `扫描镜像归档${scan.members_scanned}个成员（Key/control/PG密码/DSN）、${files}个Git跟踪文件、frontend/dist及${reportAudit.result.files_scanned}份当轮公开证据；未发现运行凭据。`, evidence_paths: [evidence], tracked_file_count: files, artifact_audit: reportAudit.result };
  });
  return suite.finish();
}
main(process.argv[process.argv.indexOf('--context') + 1]).then((code) => { process.exitCode = code; }).catch((error) => { console.error(`【quality】工程错误：${error.message}`); process.exitCode = 2; });
