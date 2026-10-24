import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runtimeInventory, storageInventory } from './runtime-inventory.mjs';

test('运行时记录App和工具实际解析依赖及前后端不同Node版本，不发布容器Env', async () => {
  const session = { run_id: 'synthetic-run', owner_token: 'synthetic-owner' };
  const labels = { 'io.sesrag.test.run_id': session.run_id, 'io.sesrag.test.owner': session.owner_token, 'com.docker.compose.project': 'project' };
  const docker = async (args) => {
    if (args[0] === 'compose') return '5.1.1';
    if (args[0] === 'ps') return args.at(-1).split('=').at(-1);
    if (args[0] === 'inspect') return JSON.stringify([{ Config: { Labels: labels, Env: ['SECRET=DO_NOT_PUBLISH'] }, Image: 'sha256:123' }]);
    if (args[0] === 'image') return JSON.stringify([{ RepoDigests: ['synthetic@sha256:123'] }]);
    return args.includes('node') ? 'v20.20.2' : JSON.stringify({ python_version: '3.12.13', packages: [{ name: 'synthetic', version: '1.0' }] });
  };
  const result = await runtimeInventory(session, 'project', { docker, command: async () => ({ code: 0, stdout: '7.6.5' }) });
  assert.equal(result.versions.powershell, '7.6.5');
  assert.equal(result.versions.node_frontend, 'v20.20.2');
  assert.equal(result.dependencies.app.packages[0].name, 'synthetic');
  assert.match(result.dependencies.tools.sha256, /^[a-f0-9]{64}$/);
  assert.doesNotMatch(JSON.stringify(result), /DO_NOT_PUBLISH|SECRET=/);
});

test('运行时清单不能exec到不属于当前project的容器', async () => {
  let executed = false;
  const docker = async (args) => {
    if (args[0] === 'compose') return '5';
    if (args[0] === 'ps') return 'container';
    if (args[0] === 'exec') executed = true;
    return JSON.stringify([{ Config: { Labels: {} } }]);
  };
  await assert.rejects(runtimeInventory({ run_id: 'run', owner_token: 'owner' }, 'project', {
    docker, command: async () => ({ code: 0, stdout: '7.6' }),
  }), /归属/);
  assert.equal(executed, false);
});

test('空间清单列明缓存与报告，不进入符号链接且不执行删除', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-space-'));
  try {
    fs.mkdirSync(path.join(root, '.cache/frozen-builds'), { recursive: true });
    fs.mkdirSync(path.join(root, 'artifacts'));
    fs.writeFileSync(path.join(root, '.cache/frozen-builds/image.tar'), '12345');
    fs.writeFileSync(path.join(root, 'artifacts/report.json'), '{}');
    const result = storageInventory(root);
    assert.equal(result.frozen_builds.bytes, 5);
    assert.equal(result.cache.bytes, 5);
    assert.equal(result.artifacts.bytes, 2);
    assert.equal(result.docker_shared_cache.bytes, null);
    assert.ok(fs.existsSync(path.join(root, '.cache/frozen-builds/image.tar')));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
