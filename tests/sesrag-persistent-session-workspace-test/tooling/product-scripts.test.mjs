import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { parseCases, suiteRoot, evidenceSecrets, redactEvidence } from './product-category.mjs';
import { isCurrentBarrier, releaseThenRestore } from '../specific_test_script/support.mjs';
import { runCommand, cleanChildEnvironment } from './process-registry.mjs';
import { isExpectedToolExit, finalizeLifecycleCase } from './orchestrator.mjs';
import { validateManifest } from './preflight.mjs';
import { latencyInterval, nearestRank } from '../specific_test_script/performance-tests.mjs';

test('八分类登记104例且逐例需求映射非空，范围表达式正确展开', () => {
  const manifest = JSON.parse(fs.readFileSync(new URL('../specific_test_script/manifest.json', import.meta.url)));
  const summary = validateManifest(manifest, suiteRoot); assert.equal(summary.case_count, 104);
  for (const category of manifest.categories) assert.deepEqual(parseCases(category.category).map((item) => item.case_id), category.case_ids);
  assert.ok(parseCases('session').find((item) => item.case_id === 'SES_002').requirements.includes('FR-TH-01'));
});
test('性能nearest-rank保留慢样本，区间交叠不得通过', () => {
  assert.equal(nearestRank([...Array(28).fill(10), 1100, 1200]), 1100);
  assert.equal(latencyInterval({ L: 0, U: 5, D_low: 900, D_high: 990 }).status, 'passed');
  assert.equal(latencyInterval({ L: 0, U: 5, D_low: 1100, D_high: 1200 }).status, 'failed');
  assert.equal(latencyInterval({ L: 0, U: 100, D_low: 1050, D_high: 1200 }).status, 'blocked');
});
test('已结束和上一配置的Provider屏障不能归给新用例', () => {
  const item = { model: 'ws-http-a', request_seq: 9, waiting_release: true, finished: false };
  assert.equal(isCurrentBarrier(item, 'ws-http-a', 8), true);
  assert.equal(isCurrentBarrier({ ...item, finished: true }, 'ws-http-a', 8), false);
  assert.equal(isCurrentBarrier(item, 'ws-http-a', 9), false);
  assert.equal(isCurrentBarrier(item, 'ws-http-b', 8), false);
});
test('Provider释放失败仍执行服务启动及就绪，原始释放错误不能变成成功', async () => {
  const calls = []; const releaseError = new Error('synthetic-release-failed');
  await assert.rejects(releaseThenRestore(async () => { calls.push('release'); throw releaseError; }, async () => { calls.push('start'); calls.push('ready'); }), (error) => error === releaseError);
  assert.deepEqual(calls, ['release', 'start', 'ready']);
  const restoreError = new Error('synthetic-restore-failed');
  await assert.rejects(releaseThenRestore(async () => {}, async () => { throw restoreError; }), (error) => error === restoreError);
});
test('label内禁用模型用原生属性和真实键盘验证；缺disabled必须失败', async () => {
  const result = await runCommand(process.execPath, ['--input-type=module', '-e', `
    import assert from 'node:assert/strict';
    import {openBrowser,assertUnavailableModel} from './specific_test_script/browser-support.mjs';
    const browser=await openBrowser();
    try {
      const page=await browser.newPage();
      await page.setContent('<div class="workspace-controls"><select><option>分支</option></select><label>模型<select><option value="a">A</option><option value="b" disabled>B（不可用）</option><option value="c">C</option></select></label></div>');
      const observed=await assertUnavailableModel(page,'b','不可用');
      assert.deepEqual([...new Set(observed.keyboard_selections)].sort(),['a','c']);
      await page.locator('option[value="b"]').evaluate(e=>e.disabled=false);
      await assert.rejects(assertUnavailableModel(page,'b','不可用'),/原生disabled/);
      console.log('原生禁用、双向键盘选择及去掉disabled负例均已验证');
    } finally {await browser.close();}
  `], { cwd: suiteRoot, timeoutMs: 30000, env: { ...cleanChildEnvironment(), PLAYWRIGHT_BROWSERS_PATH: path.join(suiteRoot, '.cache/ms-playwright') } });
  assert.equal(result.code, 0, result.output); assert.equal(result.timedOut, false); assert.equal(result.truncated, false);
});
test('公开证据首次序列化前即删除裸PG密码和其余四类动态凭据', () => {
  const credentials = ['synthetic-pg-password', 'synthetic-control-token', 'synthetic-model-key', 'postgresql+psycopg://sesrag:synthetic-pg-password@postgres/db'];
  const secrets = evidenceSecrets({ WS_EVIDENCE_SECRETS: JSON.stringify(credentials) });
  const raw = { actual: credentials.join(' '), evidence: [{ message: credentials[0] }], [credentials[1]]: 'value' };
  const serialized = JSON.stringify(redactEvidence(raw, secrets));
  for (const secret of credentials) assert.ok(!serialized.includes(secret));
  assert.ok(serialized.includes('已脱敏'));
  assert.throws(() => evidenceSecrets({ WS_EVIDENCE_SECRETS: '[123]' }));
});
test('仅明确工具退出19算预期失败，Docker异常/超时/截断不能冒充', () => {
  assert.equal(isExpectedToolExit({ commandExitCode: 19, timedOut: false, truncated: false, signal: null }), true);
  for (const error of [{}, { commandExitCode: 125 }, { commandExitCode: 19, timedOut: true }, { commandExitCode: 19, truncated: true }, { commandExitCode: 19, signal: 'SIGKILL' }]) assert.equal(isExpectedToolExit(error), false);
});
test('质量分类清理证据缺失/损坏只结算失败，不阻断全轮最终摘要', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-finalize-guard-'));
  try {
    const quality = path.join(directory, 'categories/quality'); fs.mkdirSync(quality, { recursive: true });
    for (const malformed of [false, true]) {
      const report = { cases: [{ case_id: 'QLT_005', status: 'blocked', reason_code: 'AWAITING_OUTER_CLEANUP', evidence_paths: [] }], evidence: [] };
      fs.writeFileSync(path.join(quality, 'result.json'), JSON.stringify(report));
      if (malformed) fs.writeFileSync(path.join(quality, 'cleanup.json'), '{bad');
      const state = { artifacts: directory, session: { source_unchanged: true, secret_values: [], category_counts: { blocked: 1, failed: 0 } } };
      assert.doesNotThrow(() => finalizeLifecycleCase(state, { status: 'passed' }));
      assert.equal(JSON.parse(fs.readFileSync(path.join(quality, 'result.json'))).cases[0].status, 'failed');
      assert.equal(state.session.category_counts.failed, 1);
    }
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});
