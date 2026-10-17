import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { assert, execute, executeTree, repoRoot } from '../lib/category-kit.mjs';
import { poll } from '../lib/category-kit.mjs';

export function parseScenarioOutput(result) {
  assert.equal(result.code, 0, 'PG专项进程失败，见原始证据');
  const lines = result.stdout.split(/\r?\n/).filter(line => line.startsWith('PG_SCENARIO:'));
  assert.equal(lines.length, 1, '专项必须恰好输出一个结果');
  const data = JSON.parse(lines[0].slice('PG_SCENARIO:'.length));
  assert.equal(data.status, 'passed', '专项存在失败断言');
  assert.ok(data.assertions?.length > 0, '不能以空断言通过');
  return data;
}

export function resourceIdentity(project, runId, token) {
  assert.match(project, /^sesrag-demo-smoke-[a-z0-9-]+$/);
  assert.match(runId, /^[a-z0-9][a-z0-9-]{0,100}$/);
  assert.match(token, /^[a-f0-9]{8}$/);
  return { name: `${project}-5a-${token}`, project, parent_run_id: runId,
    labels: {'com.docker.compose.project': project, 'sesrag.smoke.run_id': runId, 'sesrag.smoke.purpose': 'execution-harness'} };
}

export function registerResource(ctx, resource, status) {
  // 先登记确定名称及标签，再创建；父分类硬杀时5d能按同一身份回收。
  const target = path.join(ctx.args.RuntimeDir, 'execution-resources.json');
  const registry = fs.existsSync(target) ? JSON.parse(fs.readFileSync(target, 'utf8')) :
    {schema_version: 1, parent_run_id: ctx.args.RunId, project: ctx.context.compose_project, containers: []};
  assert.equal(registry.parent_run_id, ctx.args.RunId);
  assert.equal(registry.project, ctx.context.compose_project);
  const entry = registry.containers.find(item => item.name === resource.name);
  if (entry) Object.assign(entry, {status, updated_at: new Date().toISOString()});
  else registry.containers.push({...resource, status, updated_at: new Date().toISOString()});
  fs.writeFileSync(target + '.tmp', JSON.stringify(registry, null, 2), 'utf8');
  fs.renameSync(target + '.tmp', target);
}

export function closeResource(ctx, resource) {
  const inspected = execute('docker', ['inspect', resource.name, '--format', '{{json .Config.Labels}}'], {timeoutMs: 10000});
  if (inspected.code === 0) {
    const labels = JSON.parse(inspected.stdout);
    for (const [key, value] of Object.entries(resource.labels)) assert.equal(labels[key], value, '容器标签不匹配，拒绝删除');
    assert.equal(execute('docker', ['rm', '-f', resource.name], {timeoutMs: 15000}).code, 0);
  } else {
    // inspect失败必须以精确列表为空确认，不能把Docker不可用当成已清理。
    const listed = execute('docker', ['ps', '-a', '--filter', `name=^/${resource.name}$`, '--format', '{{.Names}}'], {timeoutMs: 10000});
    assert.equal(listed.code, 0); assert.equal(listed.stdout.trim(), '');
  }
  registerResource(ctx, resource, 'closed');
}

export async function pgScenario(ctx, scenario, {timeoutMs = 90000} = {}) {
  assert.match(scenario, /^[a-z0-9-]+$/);
  const token = randomUUID().replaceAll('-', '').slice(0, 8);
  const resource = resourceIdentity(ctx.context.compose_project, ctx.args.RunId, token);
  registerResource(ctx, resource, 'planned');
  const args = ['run', '--rm', '--name', resource.name, '--network', `${resource.project}_default`,
    ...Object.entries(resource.labels).flatMap(([key, value]) => ['--label', `${key}=${value}`]),
    '--volume', `${repoRoot.replaceAll('\\', '/')}:/work:ro`, '--workdir', '/work',
    '--env', 'DATABASE_URL', '--env', 'PYTHONPATH=/work', '--env', 'PYTHONUNBUFFERED=1',
    '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', `PG_SCENARIO_TOKEN=${token}`,
    '--entrypoint', 'python', `${resource.project}-backend:local`, 'tests/demo-smoke/tooling/pg-execution.py', scenario];
  try {
    const result = await executeTree('docker', args, {timeoutMs, env: {DATABASE_URL: ctx.env.DATABASE_URL}});
    const evidence = [ctx.evidence(`execution/${scenario}-${token}.log`, result.stdout + result.stderr),
      ctx.evidence(`execution/${scenario}-${token}-process.json`, {code: result.code, timed_out: result.timed_out, resource})];
    return {...parseScenarioOutput(result), evidence};
  } finally { closeResource(ctx, resource); }
}

export async function startControlledWorker(ctx, settings = {}, {frontend = false} = {}) {
  const allowed = new Set(['MOCK_PROVIDER','MODEL_BASE_URL','MODEL_API_KEY','MODEL_NAME','EMBEDDING_MODEL_NAME','RAG_TOP_K','TASK_DEADLINE','TASK_LEASE_TTL','TASK_HEARTBEAT_INTERVAL','WORKER_SHUTDOWN_GRACE']);
  for (const key of Object.keys(settings)) assert.ok(allowed.has(key), '控制器只接受固定测试配置');
  const token = randomUUID().replaceAll('-', '').slice(0, 8);
  const resource = resourceIdentity(ctx.context.compose_project, ctx.args.RunId, token);
  registerResource(ctx, resource, 'planned');
  try {
    const result = execute('docker', ['run', '-d', '--rm', '--name', resource.name,
      '--network', `${resource.project}_default`, '-p', '127.0.0.1::8765',
      ...Object.entries(resource.labels).flatMap(([key, value]) => ['--label', `${key}=${value}`]),
      '--volume', `${repoRoot.replaceAll('\\', '/')}:/work:ro`, '--workdir', '/work',
      '--env', 'DATABASE_URL', '--env', 'PYTHONPATH=/work', '--env', 'PYTHONDONTWRITEBYTECODE=1',
      '--env', `OWNER_ID=${ctx.context.owner_id}`,
      ...Object.keys(settings).flatMap(key => ['--env', key]),
    '--env', `PG_SCENARIO_TOKEN=${token}`, '--entrypoint', 'python', `${resource.project}-backend:local`,
      frontend ? 'tests/demo-smoke/tooling/frontend-controller.py' : 'tests/demo-smoke/tooling/worker-controller.py'], {timeoutMs: 15000, env: {DATABASE_URL: ctx.env.DATABASE_URL,...Object.fromEntries(Object.entries(settings).map(([key,value])=>[key,String(value)]))}});
    assert.equal(result.code, 0);
    const port = execute('docker', ['port', resource.name, '8765/tcp'], {timeoutMs: 10000});
    assert.equal(port.code, 0); assert.match(port.stdout.trim(), /^127\.0\.0\.1:\d+$/);
    const baseUrl = 'http://' + port.stdout.trim();
    const request = async (route, body) => {
      const response = await fetch(baseUrl + route, {method: body === undefined ? 'GET' : 'POST',
        headers: {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(30000)});
      assert.equal(response.status, 200); return response.json();
    };
    const state = await poll(async () => {try { return await request('/__test/status'); } catch { return null; }}, 20000);
    registerResource(ctx, resource, 'running');
    return {baseUrl, resource, controllerPid: state.controller_pid,
      start: (stage='delta') => request('/__test/start', {stage}),
      status: () => request('/__test/status'),
      awaitReached: () => poll(async () => {const s = await request('/__test/status'); return s.reached ? s : null;}, 15000),
      facts: runId => request('/__test/facts/' + runId),
      release: () => request('/__test/release', {}), stop: () => request('/__test/stop', {}),
      close: async () => {
        try {const current = await request('/__test/status'); if (current.worker_pid) await request('/__test/release', {}); if (current.running) await request('/__test/stop', {});}
        finally { const log = execute('docker', ['logs', resource.name], {timeoutMs: 10000}); ctx.evidence(`execution/controller-${token}.log`, log.stdout + log.stderr); closeResource(ctx, resource); }
      }};
  } catch (error) { closeResource(ctx, resource); throw error; }
}
