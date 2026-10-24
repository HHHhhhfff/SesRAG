import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { SUITE_ROOT, validateManifest } from './preflight.mjs';

// 任务2的注册门禁自测，不执行SES_001～QLT_006产品用例。
function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-catalog-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'specific_test_script'));
  fs.copyFileSync(path.join(SUITE_ROOT, 'test-cases.md'), path.join(root, 'test-cases.md'));
  fs.writeFileSync(path.join(root, 'specific_test_script/probe.mjs'), 'process.exit(2);');
  return { root, manifest: JSON.parse(fs.readFileSync(path.join(SUITE_ROOT, 'specific_test_script/manifest.json'))) };
}

test('总入口拒绝将八个必需分类降为非必需', (t) => {
  const { root, manifest } = fixture(t);
  manifest.categories[0].required = false;
  assert.throws(() => validateManifest(manifest, root), /必需/);
});

test('ready分类遗漏SES用例必须在部署前拒绝', (t) => {
  const { root, manifest } = fixture(t);
  Object.assign(manifest.categories[0], { status: 'ready', script: 'specific_test_script/probe.mjs', case_ids: ['SES_001'] });
  assert.throws(() => validateManifest(manifest, root), /用例.*不完整|缺失/);
});

test('ready分类不能登记另一分类或不存在的用例编号', (t) => {
  const { root, manifest } = fixture(t);
  for (const id of ['CTX_001', 'SES_999']) {
    Object.assign(manifest.categories[0], { status: 'ready', script: 'specific_test_script/probe.mjs', case_ids: [id] });
    assert.throws(() => validateManifest(manifest, root), /用例.*不完整|缺失|未知/);
  }
});

test('总入口拒绝指向外部脚本的链接', (t) => {
  const { root, manifest } = fixture(t);
  const outside = path.join(root, 'outside');
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, 'probe.mjs'), 'process.exit(2);');
  const target = path.join(root, 'specific_test_script/linked');
  fs.symlinkSync(outside, target, process.platform === 'win32' ? 'junction' : 'dir');
  Object.assign(manifest.categories[0], { status: 'ready', script: 'specific_test_script/linked/probe.mjs', case_ids: Array.from({ length: 18 }, (_, i) => `SES_${String(i + 1).padStart(3, '0')}`) });
  assert.throws(() => validateManifest(manifest, root), /链接|越界/);
});

test('数据库和Redis故障控制只能作用于run分类自己的服务', async (t) => {
  const { resourceHelper } = await import('./orchestrator.mjs');
  const { runPath } = await import('./resources.mjs');
  const { processIdentity } = await import('./process-registry.mjs');
  const run = 'ws-20261022t000000z-caf01234';
  const runtime = runPath('runtime', run);
  const artifacts = runPath('artifacts', run);
  const project = 'sesrag-ws-caf01234-run';
  fs.mkdirSync(runtime, { recursive: true });
  fs.mkdirSync(path.join(artifacts, 'diagnostics'), { recursive: true });
  t.after(() => { fs.rmSync(runtime, { recursive: true, force: true }); fs.rmSync(artifacts, { recursive: true, force: true }); });
  const session = { run_id: run, owner_token: 'fixture-owner', projects: [project], active_category: 'run', active_project: project,
    main_process: processIdentity(process.pid), engine: { id: 'fixture-engine', context: 'fixture-context' }, secret_values: [] };
  fs.writeFileSync(path.join(runtime, 'session.json'), JSON.stringify(session));
  const calls = [];
  const adapters = {
    engineIdentity: async () => session.engine,
    runCompose: async (_, target, args) => { calls.push({ target, args }); return args[0] === 'ps' ? 'fixture-container' : 'controlled'; },
    docker: async () => JSON.stringify([{ Config: { Labels: { 'io.sesrag.test.run_id': run, 'io.sesrag.test.owner': session.owner_token, 'com.docker.compose.project': project } } }]),
  };
  for (const service of ['postgres', 'redis']) {
    for (const action of ['stop', 'start']) {
      const result = await resourceHelper({ runId: run, category: 'run', service, action }, adapters);
      assert.equal(result.status, 'passed');
      assert.equal(calls.at(-1).target, project);
      assert.equal(calls.at(-1).args.at(-1), service);
    }
  }
});

test('其他分类不能停启数据库或Redis，拒绝发生在读取账本和Docker之前', async () => {
  const { resourceHelper } = await import('./orchestrator.mjs');
  for (const service of ['postgres', 'redis']) {
    await assert.rejects(resourceHelper({ runId: 'ws-20261022t000000z-caf01234', category: 'model', service, action: 'stop' }), /仅.*run/);
  }
});
