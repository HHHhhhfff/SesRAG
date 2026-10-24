import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { REPO_ROOT, validateManifest } from './preflight.mjs';
import {
  buildRunSummary,
  sanitizeText,
  assertSafeArtifactPath,
} from './report.mjs';

const now = '2026-10-21T00:00:00.000Z';

test('Environment 成功只表示基础设施通过，不代表产品验收通过', () => {
  const result = buildRunSummary({
    run_id: 'ws-20261021t000000z-abcdef12', mode: 'Environment',
    started_at: now, finished_at: now, environment_status: 'passed',
    cleanup_status: 'passed', source_unchanged: true, required_categories: ['session'],
    selected_categories: [], counts: { passed: 0, failed: 0, blocked: 0, not_run: 0, harness_error: 0 },
  });
  assert.equal(result.product_acceptance, 'not_run');
  assert.equal(result.final_exit_code, 0);
});

test('All 模式遇到 planned 分类必须阻止覆盖被误报为完整', () => {
  const result = buildRunSummary({
    run_id: 'ws-20261021t000000z-abcdef12', mode: 'All',
    started_at: now, finished_at: now, environment_status: 'not_run',
    cleanup_status: 'not_required', source_unchanged: true,
    required_categories: ['session'], selected_categories: [],
    unready_categories: ['session'],
    counts: { passed: 0, failed: 0, blocked: 0, not_run: 1, harness_error: 0 },
  });
  assert.equal(result.product_acceptance, 'incomplete');
  assert.equal(result.final_exit_code, 3);
});

test('清理失败优先使用退出码 4', () => {
  const result = buildRunSummary({
    run_id: 'ws-20261021t000000z-abcdef12', mode: 'Environment',
    started_at: now, finished_at: now, environment_status: 'passed',
    cleanup_status: 'failed', source_unchanged: true,
    required_categories: [], selected_categories: [],
    counts: { passed: 0, failed: 0, blocked: 0, not_run: 0, harness_error: 0 },
  });
  assert.equal(result.final_exit_code, 4);
});

test('发布前文本脱敏移除本轮秘密、Bearer 值和宿主绝对路径', () => {
  const clean = sanitizeText(
    'key=secret-value Authorization: Bearer control-token D:\\private\\project',
    ['secret-value', 'control-token'],
  );
  assert.doesNotMatch(clean, /secret-value|control-token|D:\\private/);
});

test('证据路径只能是本轮 artifact 下的相对路径', () => {
  assert.equal(assertSafeArtifactPath('categories/session/result.json'), true);
  assert.throws(() => assertSafeArtifactPath('../other/run.json'));
  assert.throws(() => assertSafeArtifactPath('D:/outside/report.json'));
});

test('源码指纹根必须包含当前产品及迁移文件', () => {
  assert.ok(fs.existsSync(path.join(REPO_ROOT, 'backend/app.py')));
  assert.ok(fs.existsSync(path.join(REPO_ROOT, 'alembic.ini')));
});

test('无动态秘密清单时仍清洗常用认证字段并保留字段名', () => {
  assert.equal(sanitizeText('api_key=abc password:def MODEL_API_KEY=ghi'),
    'api_key=[已脱敏] password=[已脱敏] MODEL_API_KEY=[已脱敏]');
});

test('manifest 不得把 planned 分类绑定空壳产品脚本', () => {
  const manifest = JSON.parse(fs.readFileSync(new URL('../specific_test_script/manifest.json', import.meta.url)));
  Object.assign(manifest.categories[0], { status: 'planned', case_ids: [] });
  manifest.categories[0].script = 'specific_test_script/session-tests.mjs';
  assert.throws(() => validateManifest(manifest), /planned/);
});

test('资源删除拒绝逃逸 run_id、错误标签与错误 Engine', async () => {
  const { runPath, assertOwnership, assertEngine } = await import('./resources.mjs');
  assert.throws(() => runPath('runtime', '../outside'));
  assert.throws(() => runPath('runtime', ''));
  assert.throws(() => assertOwnership({ 'io.sesrag.test.owner': 'other' }, { run_id: 'r', owner_token: 'o' }));
  assert.throws(() => assertEngine({ id: 'a', context: 'c' }, { id: 'b', context: 'c' }));
});

test('分类协议拒绝缺失、重复、错身份与退出码不符的结果', async () => {
  const { validateCategoryResult } = await import('./category-runner.mjs');
  const context = { run_id: 'ws-20261021t000000z-abcdef12', environment_id: 'e', category: 'session', expected_case_ids: ['C1'] };
  const one = { case_id: 'C1', test_point_ids: ['TP1'], requirement_ids: ['FR-TH-01'], title: '样本', type: '框架', status: 'passed', expected: '正常', actual: '实收正常', reason_code: null, reason: null, evidence_paths: [], duration_ms: 1 };
  const value = { schema_version: 1, run_id: context.run_id, environment_id: 'e', category: 'session', started_at: now, finished_at: now, status: 'passed', cases: [one], evidence: [] };
  assert.equal(validateCategoryResult(value, context, '.', 0).status, 'passed');
  assert.throws(() => validateCategoryResult({ ...value, cases: [] }, context, '.', 0));
  assert.throws(() => validateCategoryResult({ ...value, cases: [one, one] }, context, '.', 0));
  assert.throws(() => validateCategoryResult({ ...value, run_id: 'ws-20261021t000000z-12345678' }, context, '.', 0));
  assert.throws(() => validateCategoryResult(value, context, '.', 1));
});

test('分类 exit0 缺报告及超时都不能通过', async () => {
  const { invokeCategoryProcess } = await import('./category-runner.mjs');
  const os = await import('node:os');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-runner-'));
  try {
    await assert.rejects(invokeCategoryProcess({ command: process.execPath, args: ['-e', 'process.exit(0)'], timeoutMs: 2000, resultPath: path.join(dir, 'absent.json') }), /报告/);
    await assert.rejects(invokeCategoryProcess({ command: process.execPath, args: ['-e', 'setInterval(()=>{},1000)'], timeoutMs: 150, resultPath: path.join(dir, 'absent.json') }), /超时/);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('环境工具错误保留退出码2，不得被环境受限覆盖', () => {
  const result = buildRunSummary({ run_id: 'ws-20261021t000000z-abcdef12', mode: 'Environment',
    started_at: now, finished_at: now, environment_status: 'failed', cleanup_status: 'passed', original_exit_code: 2 });
  assert.equal(result.final_exit_code, 2);
});

test('报告写入预先准备输出目录', async () => {
  const { writeRunReport } = await import('./report.mjs');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-report-'));
  try {
    const target = path.join(root, 'new', 'artifacts');
    writeRunReport({ run_id: 'ws-20261021t000000z-abcdef12', mode: 'Environment', started_at: now,
      finished_at: now, environment_status: 'passed', cleanup_status: 'passed' }, target);
    assert.ok(fs.existsSync(path.join(target, 'summary.json')));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('已中断命令不再创建子进程', async () => {
  const { runCommand } = await import('./process-registry.mjs');
  const controller = new AbortController(); controller.abort();
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-abort-'));
  const marker = path.join(root, 'started');
  try {
    await assert.rejects(runCommand(process.execPath, ['-e', `require('fs').writeFileSync(${JSON.stringify(marker)}, 'x')`],
      { signal: controller.signal }), /中断/);
    assert.equal(fs.existsSync(marker), false);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('命令分块输出保持UTF8，发布日志先脱敏且不继承开发配置', async () => {
  const { runCommand } = await import('./process-registry.mjs');
  process.env.WS_TEST_FROM_DEVELOPMENT = 'bad';
  process.env.COMPOSE_PROJECT_NAME = 'development';
  process.env.MODEL_API_KEY = 'development-secret';
  try {
    const result = await runCommand(process.execPath, ['-e', "const b=Buffer.from('中文');process.stdout.write(b.subarray(0,1));setTimeout(()=>{process.stdout.write(b.subarray(1));process.stdout.write(JSON.stringify([process.env.WS_TEST_FROM_DEVELOPMENT,process.env.COMPOSE_PROJECT_NAME,process.env.MODEL_API_KEY]));},30)"]);
    assert.match(result.output, /^中文\[null,null,null\]$/);
  } finally { delete process.env.WS_TEST_FROM_DEVELOPMENT; delete process.env.COMPOSE_PROJECT_NAME; delete process.env.MODEL_API_KEY; }
});

test('错误owner资源必须在Compose down之前被拒绝', async () => {
  const { cleanupResources } = await import('./resources.mjs');
  const run = 'ws-20261021t000000z-abcdef12'; let down = false; const removed = [];
  const session = { run_id: run, owner_token: 'owner', engine: { id: 'engine', context: 'context' }, projects: ['project'], images: [], before: {} };
  const fakeDocker = async (args) => {
    if (args.includes('inspect')) return JSON.stringify([{ Config: { Labels: { 'io.sesrag.test.run_id': run, 'io.sesrag.test.owner': 'wrong', 'com.docker.compose.project': 'project' } } }]);
    if (args.includes('rm')) { removed.push(args); return ''; }
    return args[0] === 'ps' ? 'container' : '';
  };
  const result = await cleanupResources(session, async () => { down = true; }, { docker: fakeDocker,
    engineIdentity: async () => session.engine, snapshot: async () => ({ containers: ['container'], networks: [], volumes: [] }) });
  assert.equal(down, false); assert.equal(removed.length, 0); assert.equal(result.status, 'failed');
});

test('缺登记ID的镜像不能仅凭同名tag删除', async () => {
  const { cleanupResources } = await import('./resources.mjs');
  const run = 'ws-20261021t000000z-abcdef12'; let removed = false;
  const session = { run_id: run, owner_token: 'owner', engine: { id: 'engine', context: 'context' }, projects: [], images: [{ tag: `sesrag-ws-app:${run}`, id: null }], before: {} };
  const fakeDocker = async (args) => {
    if (args.includes('inspect')) return JSON.stringify([{ Id: 'sha256:other', Config: { Labels: {} } }]);
    if (args[0] === 'image' && args.includes('ls')) return 'sha256:other';
    if (args.includes('rm')) removed = true;
    return '';
  };
  const result = await cleanupResources(session, undefined, { docker: fakeDocker, engineIdentity: async () => session.engine,
    snapshot: async () => ({ containers: [], networks: [], volumes: [] }) });
  assert.equal(removed, false); assert.equal(result.status, 'failed');
});

test('初始化失败也会释放自身锁和临时目录并生成报告', async () => {
  const { mainRun } = await import('./orchestrator.mjs');
  const lockRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-lock-'));
  let state;
  const code = await mainRun({ mode: 'Environment', categories: [], holdSeconds: 0 }, {
    initialize: async (value) => {
      state = value;
      state.lockFile = path.join(lockRoot, 'active.lock');
      fs.mkdirSync(state.runtime, { recursive: true }); fs.mkdirSync(state.temp, { recursive: true });
      fs.writeFileSync(state.lockFile, JSON.stringify({ run_id: state.session.run_id })); state.ownsLock = true;
      throw new Error('初始化替身失败');
    },
  });
  try {
    assert.equal(code, 2); assert.equal(fs.existsSync(state.runtime), false);
    assert.equal(fs.existsSync(state.temp), false); assert.equal(fs.existsSync(state.lockFile), false);
    const result = JSON.parse(fs.readFileSync(path.join(state.artifacts, 'summary.json'), 'utf8'));
    assert.equal(result.cleanup_status, 'passed'); assert.equal(result.environment_status, 'failed');
  } finally { if (state) fs.rmSync(state.artifacts, { recursive: true, force: true }); fs.rmSync(lockRoot, { recursive: true, force: true }); }
});

test('采证失败必须仍然清理，不能环境passed或exit0', async () => {
  const { mainRun } = await import('./orchestrator.mjs');
  let state; let cleaned = false;
  const code = await mainRun({ mode: 'Environment', categories: [], holdSeconds: 0 }, {
    initialize: async (value) => { state = value; }, runEnvironment: async () => {},
    collectEvidence: async () => { throw new Error('采证替身失败'); },
    cleanup: async () => { cleaned = true; return { status: 'passed', residual: {}, actions: [], errors: [] }; },
  });
  try {
    assert.equal(cleaned, true); assert.equal(code, 2);
    const result = JSON.parse(fs.readFileSync(path.join(state.artifacts, 'summary.json'), 'utf8'));
    assert.equal(result.environment_status, 'failed'); assert.equal(result.product_acceptance, 'not_run');
  } finally { if (state) fs.rmSync(state.artifacts, { recursive: true, force: true }); }
});

// 环境安全回归：清理未通过时必须保留恢复锁，防止下一轮绕过遗留资源。
for (const cleanupState of ['failed', 'unknown', 'throws']) {
  test(`清理${cleanupState}必须保留本轮锁，不能允许新运行覆盖`, async () => {
    const { mainRun } = await import('./orchestrator.mjs');
    const lockRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-cleanup-lock-')); let state;
    try {
      const code = await mainRun({ mode: 'Environment', categories: [], holdSeconds: 0 }, {
        initialize: async (value) => {
          state = value; state.lockFile = path.join(lockRoot, 'active.lock'); state.ownsLock = true;
          fs.writeFileSync(state.lockFile, JSON.stringify({ run_id: state.session.run_id }));
        },
        runEnvironment: async () => {}, collectEvidence: async () => {},
        cleanup: async () => {
          if (cleanupState === 'throws') throw new Error('框架清理异常');
          return { status: cleanupState, errors: ['资源仍需恢复核验'], residual: {}, actions: [] };
        },
      });
      assert.equal(code, 4);
      assert.equal(fs.existsSync(state.lockFile), true);
      assert.equal(JSON.parse(fs.readFileSync(state.lockFile)).run_id, state.session.run_id);
    } finally {
      if (state) fs.rmSync(state.artifacts, { recursive: true, force: true });
      fs.rmSync(lockRoot, { recursive: true, force: true });
    }
  });
}

test('进程重新托管父PID变化不能绕过活跃进程保护', async () => {
  const { processIdentity, sameProcess } = await import('./process-registry.mjs');
  const identity = processIdentity(process.pid); assert.ok(identity);
  assert.equal(sameProcess(identity, { ...identity, parent_pid: identity.parent_pid + 1 }), true);
});

test('机器JSON与子进程stderr诊断分别保留', async () => {
  const { runCommand } = await import('./process-registry.mjs');
  const result = await runCommand(process.execPath, ['-e', "process.stdout.write('{\"status\":\"passed\"}');process.stderr.write('progress');"]);
  assert.deepEqual(JSON.parse(result.stdout), { status: 'passed' });
  assert.equal(result.stderr, 'progress');
});

test('报告落盘失败不会阻止finally资源清理', async () => {
  const { mainRun } = await import('./orchestrator.mjs'); let state; let cleaned = false;
  try {
    const code = await mainRun({ mode: 'Environment', categories: [], holdSeconds: 0 }, {
      initialize: async (value) => { state = value; }, runEnvironment: async () => {},
      collectEvidence: async () => { fs.rmSync(path.join(state.artifacts, 'diagnostics'), { recursive: true }); fs.writeFileSync(path.join(state.artifacts, 'diagnostics'), 'blocked'); throw new Error('采证错误'); },
      cleanup: async () => { cleaned = true; return { status: 'passed', residual: {}, errors: [], actions: [] }; },
    });
    assert.equal(cleaned, true); assert.equal(code, 2);
  } finally { if (state) fs.rmSync(state.artifacts, { recursive: true, force: true }); }
});

test('分类runner拒绝非零退出伪造passed报告及历史遗留报告', async () => {
  const { invokeCategoryProcess } = await import('./category-runner.mjs');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-category-')); const resultPath = path.join(root, 'result.json');
  const context = { run_id: 'ws-20261021t000000z-abcdef12', environment_id: 'e', category: 'session', expected_case_ids: ['C1'] };
  const value = { schema_version: 1, ...Object.fromEntries(['run_id', 'environment_id', 'category'].map((key) => [key, context[key]])), started_at: now, finished_at: now,
    status: 'passed', evidence: [], cases: [{ case_id: 'C1', test_point_ids: ['TP1'], requirement_ids: ['FR-TH-01'], title: '框架', type: '框架', status: 'passed', expected: '正常', actual: '正常', reason_code: null, reason: null, evidence_paths: [], duration_ms: 1 }] };
  try {
    await assert.rejects(invokeCategoryProcess({ command: process.execPath, args: ['-e', `require('fs').writeFileSync(${JSON.stringify(resultPath)}, ${JSON.stringify(JSON.stringify(value))});process.exit(1)`],
      resultPath, timeoutMs: 3000, context, artifactRoot: root }), /退出码/);
    fs.writeFileSync(resultPath, JSON.stringify(value));
    await assert.rejects(invokeCategoryProcess({ command: process.execPath, args: ['-e', 'process.exit(0)'], resultPath, timeoutMs: 3000, context, artifactRoot: root }), /遗留|存在/);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('证据不能引用目录或Windows备用数据流', async () => {
  const { validateCategoryResult } = await import('./category-runner.mjs');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-evidence-')); fs.mkdirSync(path.join(root, 'diagnostics'));
  const context = { run_id: 'ws-20261021t000000z-abcdef12', environment_id: 'e', category: 'session', expected_case_ids: ['C1'] };
  const one = { case_id: 'C1', test_point_ids: ['TP1'], requirement_ids: ['FR-TH-01'], title: '框架', type: '框架', status: 'passed', expected: '正常', actual: '正常', reason_code: null, reason: null, evidence_paths: [], duration_ms: 1 };
  const value = { schema_version: 1, run_id: context.run_id, environment_id: 'e', category: 'session', started_at: now, finished_at: now, status: 'passed', cases: [one], evidence: ['diagnostics'] };
  try { assert.throws(() => validateCategoryResult(value, context, root, 0)); assert.throws(() => assertSafeArtifactPath('diagnostics/file.txt:stream')); }
  finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('中断后清理失败仍必须优先退出4', async () => {
  const { mainRun } = await import('./orchestrator.mjs'); let state;
  const code = await mainRun({ mode: 'Environment', categories: [], holdSeconds: 0 }, {
    initialize: async (value) => { state = value; }, runEnvironment: async () => { state.controller.abort(); throw new Error('捕获中断'); },
    collectEvidence: async () => {}, cleanup: async () => ({ status: 'failed', errors: ['残留'], residual: {}, actions: [] }),
  });
  try { assert.equal(code, 4); } finally { if (state) fs.rmSync(state.artifacts, { recursive: true, force: true }); }
});

test('强停恢复拒绝仍活跃主进程且不删除其目录', async () => {
  const { cleanupMode } = await import('./orchestrator.mjs');
  const { processIdentity } = await import('./process-registry.mjs');
  const { runPath } = await import('./resources.mjs');
  const run = 'ws-20261021t000000z-abcd1234'; const runtime = runPath('runtime', run);
  fs.mkdirSync(runtime, { recursive: true }); fs.writeFileSync(path.join(runtime, 'session.json'), JSON.stringify({ run_id: run, owner_token: 'owner', projects: [], main_process: processIdentity(process.pid) }));
  try { await assert.rejects(cleanupMode({ runId: run }), /活跃/); assert.equal(fs.existsSync(runtime), true); }
  finally { fs.rmSync(runtime, { recursive: true, force: true }); }
});

test('清理后幂等调用仍独立审计，不信任旧passed标记', async () => {
  const { cleanupMode } = await import('./orchestrator.mjs'); const { runPath } = await import('./resources.mjs');
  const run = 'ws-20261021t000000z-abcd5678'; const root = runPath('artifacts', run); fs.mkdirSync(root, { recursive: true });
  fs.writeFileSync(path.join(root, 'cleanup.json'), JSON.stringify({ run_id: run, status: 'passed' }));
  try { await assert.rejects(cleanupMode({ runId: run }), /身份无效|账本/); }
  finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('恢复清理异常必须更新旧成功摘要，不能留下清理通过的假象', async () => {
  const { cleanupMode } = await import('./orchestrator.mjs');
  const { runPath } = await import('./resources.mjs');
  const { writeRunReport } = await import('./report.mjs');
  const run = 'ws-20261021t000000z-abcd8888'; const runtime = runPath('runtime', run); const root = runPath('artifacts', run);
  fs.mkdirSync(runtime, { recursive: true });
  fs.writeFileSync(path.join(runtime, 'session.json'), JSON.stringify({ run_id: run, owner_token: 'owner', projects: [], processes: [], engine: null }));
  // 损坏的辅助进程账本在任何 Docker 操作前触发真实恢复异常。
  fs.writeFileSync(path.join(runtime, 'helper-processes.json'), '{invalid-json');
  writeRunReport({ run_id: run, mode: 'Cleanup', started_at: now, finished_at: now, environment_status: 'incomplete', cleanup_status: 'passed' }, root);
  try {
    assert.equal(await cleanupMode({ runId: run }), 4);
    const summary = JSON.parse(fs.readFileSync(path.join(root, 'summary.json')));
    assert.equal(summary.cleanup_status, 'unknown'); assert.equal(summary.final_exit_code, 4);
    assert.equal(summary.product_acceptance, 'not_run'); assert.ok(summary.not_run_reasons.length);
  } finally { fs.rmSync(runtime, { recursive: true, force: true }); fs.rmSync(root, { recursive: true, force: true }); }
});

test('恢复清理报告不可写仍保持退出4并明确告警', async () => {
  const { spawnSync } = await import('node:child_process');
  const { runPath } = await import('./resources.mjs');
  const { writeRunReport } = await import('./report.mjs');
  const run = 'ws-20261021t000000z-abcd7777'; const runtime = runPath('runtime', run); const root = runPath('artifacts', run);
  fs.mkdirSync(runtime, { recursive: true });
  fs.writeFileSync(path.join(runtime, 'session.json'), JSON.stringify({ run_id: run, owner_token: 'owner', projects: [], processes: [], engine: null }));
  fs.writeFileSync(path.join(runtime, 'helper-processes.json'), '{invalid-json');
  writeRunReport({ run_id: run, mode: 'Cleanup', started_at: now, finished_at: now, environment_status: 'incomplete', cleanup_status: 'passed' }, root);
  // 用同名目录阻塞清理报告写入，验证真实CLI不会把清理异常降为普通工具错误。
  fs.mkdirSync(path.join(root, 'cleanup.json'));
  try {
    const result = spawnSync(process.execPath, [path.join(REPO_ROOT, 'tests/sesrag-persistent-session-workspace-test/tooling/orchestrator.mjs'), '--mode', 'Cleanup', '--run-id', run],
      { encoding: 'utf8', timeout: 10000, windowsHide: true });
    assert.equal(result.status, 4);
    assert.match(result.stderr, /清理状态报告写入失败/);
    assert.equal(JSON.parse(fs.readFileSync(path.join(root, 'summary.json'))).cleanup_status, 'unknown');
  } finally { fs.rmSync(runtime, { recursive: true, force: true }); fs.rmSync(root, { recursive: true, force: true }); }
});

test('最后独立审计能发现删除阶段之后出现的资源', async () => {
  const { cleanupResources } = await import('./resources.mjs'); const run = 'ws-20261021t000000z-abcdef12'; let snapshots = 0;
  const session = { run_id: run, owner_token: 'owner', engine: { id: 'engine', context: 'context' }, projects: ['project'], images: [], before: {} };
  const fakeDocker = async (args) => {
    if (args.includes('inspect')) return JSON.stringify([{ Config: { Labels: { 'io.sesrag.test.run_id': run, 'io.sesrag.test.owner': 'owner', 'com.docker.compose.project': 'project' } } }]);
    return snapshots && args[0] === 'ps' ? 'late-container' : '';
  };
  const result = await cleanupResources(session, undefined, { docker: fakeDocker, engineIdentity: async () => session.engine,
    snapshot: async () => { snapshots++; return { containers: ['late-container'], networks: [], volumes: [] }; } });
  assert.equal(result.status, 'failed'); assert.deepEqual(result.residual.containers, ['late-container']);
});

test('未知镜像tag即使不存在也不能把非法账本判清理成功', async () => {
  const { cleanupResources } = await import('./resources.mjs');
  const session = { run_id: 'ws-20261021t000000z-abcdef12', owner_token: 'owner', engine: { id: 'engine', context: 'context' }, projects: [], images: [{ tag: 'development:latest', id: 'sha256:dev' }], before: {} };
  const result = await cleanupResources(session, undefined, { docker: async () => '', engineIdentity: async () => session.engine,
    snapshot: async () => ({ containers: [], networks: [], volumes: [] }) });
  assert.equal(result.status, 'failed');
});

for (const mode of ['Selected', 'All']) test(`${mode}的ready分类真实调用脚本且串行使用独立project和上下文`, async () => {
  const { mainRun } = await import('./orchestrator.mjs'); const calls = []; let state;
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-ready-')); fs.mkdirSync(path.join(fixtureRoot, 'specific_test_script'));
  fs.copyFileSync(path.join(REPO_ROOT, 'tests/sesrag-persistent-session-workspace-test/test-cases.md'), path.join(fixtureRoot, 'test-cases.md'));
  const { readCaseCatalog } = await import('./case-catalog.mjs');
  const catalog = readCaseCatalog(fixtureRoot);
  const manifest = JSON.parse(fs.readFileSync(new URL('../specific_test_script/manifest.json', import.meta.url)));
  const script = "import fs from 'node:fs';import path from 'node:path';const ctx=JSON.parse(fs.readFileSync(process.argv[process.argv.indexOf('--context')+1]));const now=new Date().toISOString();fs.writeFileSync(path.resolve(ctx.artifact_dir,'result.json'),JSON.stringify({schema_version:1,run_id:ctx.run_id,environment_id:ctx.environment_id,category:ctx.category,started_at:now,finished_at:now,status:'passed',evidence:[],cases:ctx.expected_case_ids.map(case_id=>({case_id,test_point_ids:['TP-FRAMEWORK'],requirement_ids:['FR-TH-01'],title:'框架替身',type:'框架',status:'passed',expected:'独立上下文',actual:ctx.environment_id,reason_code:null,reason:null,evidence_paths:[],duration_ms:1}))}));console.log('框架替身完成');";
  fs.writeFileSync(path.join(fixtureRoot, 'specific_test_script', 'framework.mjs'), script);
  for (const entry of manifest.categories) Object.assign(entry, { status: 'planned', script: null, case_ids: [] });
  for (const entry of mode === 'All' ? manifest.categories : manifest.categories.slice(0, 2)) Object.assign(entry, { status: 'ready', script: 'specific_test_script/framework.mjs', case_ids: catalog.categories[entry.category] });
  try {
    const code = await mainRun({ mode, categories: mode === 'All' ? [] : ['session', 'context'], holdSeconds: 0 }, {
      manifest, suiteRoot: fixtureRoot, initialize: async (value) => { state = value; fs.mkdirSync(state.runtime, { recursive: true }); },
      buildImages: async () => {}, saveFrozenBuild: async () => 'framework-fingerprint',
      prepareCategoryFixtures: async () => {},
      collectProjectEvidence: async () => {},
      setupProject: async (session, project, category) => { calls.push(`setup:${category}:${project}`); session.endpoints = { api_base_url: 'http://127.0.0.1:1234', frontend_base_url: 'http://127.0.0.1:1235', provider_control_url: 'http://127.0.0.1:1236' }; },
      cleanupProject: async (session, project, category) => { calls.push(`cleanup:${category}:${project}`); return { status: 'passed', actions: [], errors: [], residual: {} }; },
      collectEvidence: async () => {},
    });
    assert.equal(code, 0); assert.equal(calls.length, mode === 'All' ? 16 : 4);
    assert.match(calls[0], /^setup:session:/); assert.match(calls[1], /^cleanup:session:/);
    assert.match(calls[2], /^setup:context:/); assert.match(calls[3], /^cleanup:context:/);
    assert.notEqual(calls[0].split(':')[2], calls[2].split(':')[2]);
    const report = JSON.parse(fs.readFileSync(path.join(state.artifacts, 'summary.json')));
    assert.equal(report.product_acceptance, mode === 'All' ? 'passed' : 'partial');
    assert.equal(report.counts.passed, mode === 'All' ? 104 : 31);
    assert.equal(report.quality_prerequisites, mode === 'All' ? 'ready' : 'pending');
  } finally { fs.rmSync(fixtureRoot, { recursive: true, force: true }); if (state) { fs.rmSync(state.artifacts, { recursive: true, force: true }); fs.rmSync(state.runtime, { recursive: true, force: true }); fs.rmSync(state.temp, { recursive: true, force: true }); } }
});

test('已知Linux宿主根路径脱敏且保留HTTP技术地址', () => {
  const text = sanitizeText('at file:///home/test/repo/tool.mjs http://api:8000 /home/test/repo/private', [], ['/home/test/repo']);
  assert.doesNotMatch(text, /\/home\/test\/repo/); assert.match(text, /http:\/\/api:8000/);
});

test('采证工具错误优先于已经记录的产品失败', () => {
  const summary = buildRunSummary({ run_id: 'ws-20261021t000000z-abcdef12', mode: 'Selected', started_at: now, finished_at: now,
    environment_status: 'passed', cleanup_status: 'passed', counts: { failed: 1 }, original_exit_code: 2 });
  assert.equal(summary.final_exit_code, 2); assert.equal(summary.counts.failed, 1);
});

test('资源helper拒绝越界分类与非白名单服务而不调用Docker', async () => {
  const { resourceHelper } = await import('./orchestrator.mjs'); let called = false;
  const adapters = { engineIdentity: async () => { called = true; return {}; } };
  await assert.rejects(resourceHelper({ runId: 'ws-20261021t000000z-abcdef12', category: '../outside', action: 'restart', service: 'worker' }, adapters), /身份/);
  await assert.rejects(resourceHelper({ runId: 'ws-20261021t000000z-abcdef12', category: 'run', action: 'restart', service: 'frontend' }, adapters), /白名单/);
  assert.equal(called, false);
});

test('资源helper只操作当前project已核验服务并记录动作意图', async () => {
  const { resourceHelper } = await import('./orchestrator.mjs'); const { processIdentity } = await import('./process-registry.mjs'); const { runPath } = await import('./resources.mjs');
  const run = 'ws-20261021t000000z-abcd9999'; const runtime = runPath('runtime', run); const artifacts = runPath('artifacts', run); const project = 'sesrag-ws-abcd9999-run';
  fs.mkdirSync(runtime, { recursive: true }); fs.mkdirSync(path.join(artifacts, 'diagnostics'), { recursive: true });
  const session = { run_id: run, owner_token: 'owner', projects: [project], active_category: 'run', active_project: project, engine: { id: 'engine', context: 'context' }, secret_values: [], main_process: processIdentity(process.pid) };
  fs.writeFileSync(path.join(runtime, 'session.json'), JSON.stringify(session)); const calls = [];
  const adapters = { engineIdentity: async () => session.engine,
    runCompose: async (_, target, args) => { calls.push({ target, args }); return args[0] === 'ps' ? 'worker-container' : 'restarted'; },
    docker: async () => JSON.stringify([{ Config: { Labels: { 'io.sesrag.test.run_id': run, 'io.sesrag.test.owner': 'owner', 'com.docker.compose.project': project } } }]),
  };
  try {
    const result = await resourceHelper({ runId: run, category: 'run', action: 'restart', service: 'worker' }, adapters);
    assert.equal(result.status, 'passed'); assert.deepEqual(calls[1], { target: project, args: ['restart', '--timeout', '30', 'worker'] });
    const events = fs.readFileSync(path.join(runtime, 'helper-actions.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
    assert.deepEqual(events.map((item) => item.status), ['intent', 'completed']); assert.equal(events[0].operation_id, events[1].operation_id);
    await assert.rejects(resourceHelper({ runId: run, category: 'session', action: 'stop', service: 'api' }, adapters), /当前分类/);
    assert.equal(calls.length, 2);
  } finally { fs.rmSync(runtime, { recursive: true, force: true }); fs.rmSync(artifacts, { recursive: true, force: true }); }
});

test('进程创建身份不可读时仍登记未核验PID并记录退出', async () => {
  const { runCommand } = await import('./process-registry.mjs'); const events = [];
  const result = await runCommand(process.execPath, ['-e', 'setTimeout(()=>process.exit(0),200)'], {
    timeoutMs: 3000, identityReader: () => null, onProcess: (entry, active) => events.push({ ...entry, active }),
  });
  assert.equal(result.code, 0); assert.equal(events.length, 2);
  assert.equal(events[0].unverified, true); assert.equal(events[0].active, true); assert.equal(events[1].active, false);
});

test('All必须质量前提ready才能宣布完整产品验收', () => {
  const base = { run_id: 'ws-20261021t000000z-abcdef12', mode: 'All', started_at: now, finished_at: now,
    environment_status: 'passed', cleanup_status: 'passed', counts: { passed: 1 }, original_exit_code: 0 };
  for (const quality of ['pending', 'blocked']) {
    const summary = buildRunSummary({ ...base, quality_prerequisites: quality });
    assert.equal(summary.product_acceptance, 'incomplete'); assert.equal(summary.final_exit_code, 3);
  }
  assert.equal(buildRunSummary({ ...base, quality_prerequisites: 'ready' }).product_acceptance, 'passed');
});

test('分类日志超限丢失不能通过合法passed结果掩盖', async () => {
  const { invokeCategoryProcess } = await import('./category-runner.mjs'); const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-large-log-'));
  const resultPath = path.join(root, 'result.json');
  const context = { run_id: 'ws-20261021t000000z-abcdef12', environment_id: 'e', category: 'session', expected_case_ids: ['C1'] };
  const value = { schema_version: 1, run_id: context.run_id, environment_id: 'e', category: 'session', started_at: now, finished_at: now, status: 'passed', evidence: [],
    cases: [{ case_id: 'C1', test_point_ids: ['TP1'], requirement_ids: ['FR-TH-01'], title: '框架', type: '框架', status: 'passed', expected: '正常', actual: '正常', reason_code: null, reason: null, evidence_paths: [], duration_ms: 1 }] };
  try {
    await assert.rejects(invokeCategoryProcess({ command: process.execPath, args: ['-e', `require('fs').writeFileSync(${JSON.stringify(resultPath)},${JSON.stringify(JSON.stringify(value))});process.stdout.write('x'.repeat(1000));`],
      resultPath, context, artifactRoot: root, timeoutMs: 3000, maxBytes: 128 }), /日志.*超限|截断/);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('分类清理不能把本轮build project网络当作越权资源', async () => {
  const { cleanupResources } = await import('./resources.mjs'); const run = 'ws-20261021t000000z-abcdef12'; const remaining = new Set(['build-net', 'category-net']);
  const session = { run_id: run, owner_token: 'owner', engine: { id: 'engine', context: 'context' }, projects: ['category'], images: [], before: {} };
  const fakeDocker = async (args) => {
    if (args[0] === 'network' && args[1] === 'inspect') { const project = args[2] === 'build-net' ? 'build' : 'category'; return JSON.stringify([{ Labels: { 'io.sesrag.test.run_id': run, 'io.sesrag.test.owner': 'owner', 'com.docker.compose.project': project } }]); }
    if (args[0] === 'network' && args[1] === 'rm') { remaining.delete(args[2]); return ''; }
    if (args[0] === 'network' && args[1] === 'ls') return [...remaining].filter((id) => !args.includes('label=com.docker.compose.project=category') || id === 'category-net').join('\n');
    return '';
  };
  const result = await cleanupResources(session, undefined, { projectOnly: true, docker: fakeDocker, engineIdentity: async () => session.engine,
    snapshot: async () => ({ containers: [], networks: [...remaining], volumes: [] }) });
  assert.equal(result.status, 'passed'); assert.deepEqual([...remaining], ['build-net']);
});

test('父进程先退出且子孙继承管道时不能伪报已回收', async () => {
  const { runCommand, processIdentity, terminateRegistered } = await import('./process-registry.mjs');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-descendant-')); const marker = path.join(root, 'child.pid'); const entries = [];
  const descendant = `require('fs').writeFileSync(${JSON.stringify(marker)},String(process.pid));setInterval(()=>{},1000);`;
  const script = `const child=require('child_process').spawn(process.execPath,['-e',${JSON.stringify(descendant)}],{stdio:['ignore','inherit','inherit'],detached:process.platform==='win32',windowsHide:true});child.unref();const timer=setInterval(()=>{if(require('fs').existsSync(${JSON.stringify(marker)})){clearInterval(timer);process.exit(0)}},10);`;
  try {
    await assert.rejects(runCommand(process.execPath, ['-e', script], { timeoutMs: 1000, onProcess: (entry) => entries.push({ ...entry }) }), /子孙|期限|未.*退出/);
    assert.equal(fs.existsSync(marker), true); assert.equal(entries.some((entry) => entry.process_tree_unverified || entry.is_descendant), true);
  } finally {
    if (fs.existsSync(marker)) { const entry = processIdentity(Number(fs.readFileSync(marker, 'utf8'))); if (entry) terminateRegistered(entry); }
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('阶段共享总预算到期后不得再创建下一命令', async () => {
  const { runStage } = await import('./orchestrator.mjs'); const { runCommand } = await import('./process-registry.mjs');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-stage-')); const marker = path.join(root, 'started');
  try {
    await assert.rejects(runStage(5, async () => {
      await new Promise((resolve) => setTimeout(resolve, 15));
      return runCommand(process.execPath, ['-e', `require('fs').writeFileSync(${JSON.stringify(marker)},'x')`]);
    }), /阶段总期限/);
    assert.equal(fs.existsSync(marker), false);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('归属未核验的子孙记录不能被当作可安全终止身份', async () => {
  const { terminateRegistered } = await import('./process-registry.mjs');
  assert.throws(() => terminateRegistered({ pid: 2147483646, ownership_unverified: true }), /归属/);
});
