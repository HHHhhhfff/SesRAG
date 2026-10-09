import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { assert, execute, repoRoot, smokeRoot, registerNestedRun } from '../lib/category-kit.mjs';

// LIFE_001～008：所有nested run由同一正式生命周期入口创建/销毁；分类不自行Compose down。
const runner = path.join(smokeRoot, 'run-demo-smoke.ps1');
export const artifactFor = runId => ownedPath('artifacts', runId);
function ownedPath(folder, runId) {
  assert.match(runId, /^[a-z0-9][a-z0-9-]{0,100}$/);
  const root = path.resolve(smokeRoot, folder); const target = path.resolve(root, runId);
  assert.equal(path.dirname(target), root);
  if (fs.existsSync(target)) assert.ok(!fs.lstatSync(target).isSymbolicLink());
  return target;
}
export function readJson(filename) { return JSON.parse(fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, '')); }
function docker(args) {
  const result = execute('docker', args, { timeoutMs: 15000 });
  assert.equal(result.code, 0, '只读Docker生命周期诊断失败');
  return result.stdout.trim();
}
function lines(text) { return text ? text.split(/\r?\n/).filter(Boolean) : []; }
export function resourceIds(kind, project) {
  assert.match(project, /^sesrag-demo-smoke-[a-z0-9-]+$/);
  const args = kind === 'containers' ? ['ps', '-aq'] : [kind === 'networks' ? 'network' : 'volume', 'ls', '-q'];
  return lines(docker([...args, '--filter', `label=com.docker.compose.project=${project}`])).sort();
}
function containerData(ids) {
  if (!ids.length) return [];
  return JSON.parse(docker(['inspect', ...ids])).map(item => ({
    id: item.Id, name: item.Name, image_id: item.Image,
    project: item.Config.Labels?.['com.docker.compose.project'] ?? null,
    service: item.Config.Labels?.['com.docker.compose.service'] ?? null,
    ports: item.NetworkSettings.Ports,
    volumes: item.Mounts.filter(mount => mount.Type === 'volume').map(mount => mount.Name).sort(),
  })).sort((a, b) => a.id.localeCompare(b.id));
}
export function baselineResources() {
  // LIFE_001：只保存资源归属/绑定，不保存环境变量、数据库密码、宿主挂载路径或日志正文。
  return { containers: containerData(lines(docker(['ps', '-aq']))), networks: lines(docker(['network', 'ls', '-q'])).sort(), volumes: lines(docker(['volume', 'ls', '-q'])).sort() };
}
export function deployedResources(project) {
  const containers = containerData(resourceIds('containers', project));
  return { project, containers, networks: resourceIds('networks', project), volumes: resourceIds('volumes', project), mount_volumes: [...new Set(containers.flatMap(item => item.volumes))].sort(), image_tags: [`${project}-backend:local`, `${project}-frontend:local`] };
}
function scrub(text, password) {
  return password ? text.split(password).join('[已脱敏]') : text;
}
async function processChild(args, { timeoutMs = 300000, env = {}, onLine } = {}) {
  // LIFE_002/004/006：shell=false、CreateNoWindow、有界等待；超时只终止自身进程树。
  const child = spawn('pwsh', ['-NoProfile', '-File', runner, ...args], { cwd: repoRoot, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, ...env } });
  const started = performance.now(); let stdout = ''; let stderr = ''; let pending = ''; let timedOut = false;
  child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8');
  let observerError;
  child.stdout.on('data', chunk => {
    stdout += chunk; pending += chunk;
    const parts = pending.split(/\r?\n/); pending = parts.pop();
    for (const line of parts) if (onLine) { try { onLine(line); } catch (error) { observerError ??= error; } }
  });
  child.stderr.on('data', chunk => { stderr += chunk; });
  const timer = setTimeout(() => {
    timedOut = true;
    if (process.platform === 'win32') execute('taskkill', ['/PID', String(child.pid), '/T', '/F'], { timeoutMs: 15000 });
    else child.kill('SIGKILL');
  }, timeoutMs);
  let code;
  try { code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('close', value => resolve(value ?? -1)); }); }
  finally { clearTimeout(timer); }
  if (pending && onLine) { try { onLine(pending); } catch (error) { observerError ??= error; } }
  return { code, timed_out: timedOut, duration_ms: Math.round(performance.now() - started), stdout, stderr, observer_error: observerError?.message };
}
export async function runHarness(s, scenario, { category = 'all', keep = false, daemonUnavailable = false, timeoutMs = 300000, registry } = {}) {
  assert.ok(['not-ready', 'disabled', 'protocol', 'missing-script', 'nested-recovery'].includes(scenario));
  const parentProject = s.ctx.context.compose_project;
  const args = ['-HarnessScenario', scenario, '-ProjectName', 'sesrag-demo-smoke-life', '-Build:$false', '-BackendImage', `${parentProject}-backend:local`, '-FrontendImage', `${parentProject}-frontend:local`, '-Category', category, '-ApiPort', '18000', '-FrontendPort', '15173', '-WaitTimeoutSeconds', '90', '-SessionSeconds', daemonUnavailable ? '0' : '4'];
  if (keep) args.push('-KeepContainers');
  const record = { scenario, category, keep, state: null, resources: null, password: null, resource_error: null };
  const environment = daemonUnavailable ? { DOCKER_HOST: 'tcp://127.0.0.1:9', DOCKER_CONTEXT: '' } : {};
  s.note(`LIFE harness开始：scenario=${scenario}，选择=${category}，诊断保留=${keep}，daemon故障=${daemonUnavailable}`);
  const result = await processChild(args, { timeoutMs, env: environment, onLine: line => {
    const match = line.match(/^Run: ([a-z0-9-]+)；project: (sesrag-demo-smoke-[a-z0-9-]+)$/);
    if (match && !record.state) {
      assert.notEqual(match[2], parentProject); assert.notEqual(match[1], s.ctx.args.RunId);
      const runtime = ownedPath('runtime', match[1]); record.state = readJson(path.join(runtime, 'context.json'));
      record.artifact = artifactFor(match[1]);
      assert.equal(record.state.run_id, match[1]); assert.equal(record.state.compose_project, match[2]); assert.equal(record.state.marker, 'sesrag-demo-smoke-v1');
      registerNestedRun(s.ctx, record.state);
      record.password = fs.readFileSync(path.join(runtime, 'compose.env'), 'utf8').match(/^SMOKE_DB_PASSWORD=(.+)$/m)?.[1]?.trim();
      if (registry) registry.push(record);
      s.note(`LIFE新隔离run_id=${record.state.run_id}，project=${record.state.compose_project}`);
    }
    if (line.includes('隔离环境就绪') && record.state && !record.resources) {
      try { record.resources = deployedResources(record.state.compose_project); } catch { record.resource_error = '部署后只读资源快照失败'; }
      s.note(`LIFE harness就绪：run_id=${record.state.run_id}；已保存安全资源归属摘要`);
    }
  } });
  assert.ok(record.state, 'nested runner未给出可追溯的Run/context');
  assert.ok(!result.observer_error, 'nested stdout/context观察失败');
  record.process = { code: result.code, timed_out: result.timed_out, duration_ms: result.duration_ms };
  record.output = scrub(`${result.stdout}\n${result.stderr}`, record.password);
  record.artifact = artifactFor(record.state.run_id); record.summary = readJson(path.join(record.artifact, 'summary.json')); record.cleanup = readJson(path.join(record.artifact, 'cleanup.json'));
  record.trace = s.ctx.evidence(`life/nested-${record.state.run_id}.json`, { scenario, category, keep, state: record.state, process: record.process, resources: record.resources, resource_error: record.resource_error, summary: record.summary, cleanup: record.cleanup });
  s.note(`LIFE harness结束：run_id=${record.state.run_id}；exit=${result.code}；status=${record.summary.status}；证据=${record.trace}`);
  assert.ok(!result.timed_out, 'nested runner超过300秒总限时，finally将尝试本次恢复清理');
  return record;
}
export async function cleanupNested(s, record) {
  assert.notEqual(record.state.run_id, s.ctx.args.RunId); assert.notEqual(record.state.compose_project, s.ctx.context.compose_project);
  const runtime = ownedPath('runtime', record.state.run_id);
  if (!fs.existsSync(runtime)) return record;
  // LIFE_006/008：只交给正式CleanupRunId，禁止自行全局删除或接管未知project。
  const result = await processChild(['-CleanupRunId', record.state.run_id], { timeoutMs: 240000 });
  const cleanup = readJson(path.join(record.artifact, 'cleanup.json')); const summary = readJson(path.join(record.artifact, 'summary.json'));
  record.recovery = { process: { code: result.code, timed_out: result.timed_out, duration_ms: result.duration_ms }, cleanup, summary };
  s.note(`LIFE恢复清理：run_id=${record.state.run_id}；exit=${result.code}；cleanup=${cleanup.status}`);
  return record;
}
export function assertClean(record, cleanup = record.cleanup) {
  // LIFE_007：仅在nested入口已经结束后核对其精确project/捕获卷；不声称主环境已销毁。
  assert.equal(cleanup.status, 'passed');
  for (const kind of ['containers', 'networks', 'volumes']) assert.deepEqual(resourceIds(kind, record.state.compose_project), []);
  const allVolumes = lines(docker(['volume', 'ls', '-q']));
  for (const volume of record.resources?.mount_volumes ?? []) assert.ok(!allVolumes.includes(volume), '捕获的本次业务/匿名卷仍残留');
  for (const tag of [`${record.state.compose_project}-backend:local`, `${record.state.compose_project}-frontend:local`]) assert.equal(docker(['image', 'ls', '-q', tag]), '', '本次唯一镜像tag未删除');
  assert.ok(!fs.existsSync(ownedPath('runtime', record.state.run_id))); assert.ok(!fs.existsSync(ownedPath('tmp', record.state.run_id)));
  assert.ok(fs.existsSync(path.join(record.artifact, 'summary.json')));
  for (const residual of Object.values(cleanup.residuals)) assert.ok(Array.isArray(residual) && residual.length === 0, 'cleanup.json不得掩盖残留');
  return { nested_run_id: record.state.run_id, project: record.state.compose_project, zero_container_network_volume_tag_runtime_tmp: true, artifact_preserved: true };
}
export function reportFingerprint(record) {
  const names = ['summary.json', 'summary.md', 'cleanup.json', 'manifest.json'];
  return Object.fromEntries(names.map(name => [name, createHash('sha256').update(fs.readFileSync(path.join(record.artifact, name))).digest('hex')]));
}
export function isProcessPresent(pid) {
  try { process.kill(pid, 0); return true; } catch (error) { if (error.code === 'ESRCH') return false; throw error; }
}
export function inheritedImagesIntact(s) {
  for (const tag of [`${s.ctx.context.compose_project}-backend:local`, `${s.ctx.context.compose_project}-frontend:local`]) assert.ok(docker(['image', 'ls', '-q', tag]), 'nested清理不得删除主run共享源镜像tag');
}
export async function rejectedRecovery(s) {
  // LIFE_009：无部署专属目录，只写无效标记；从不提供可用于销毁主project的有效凭据。
  const runId = `life-invalid-${randomUUID().slice(0, 8)}`;
  const runtime = ownedPath('runtime', runId); const temporary = ownedPath('tmp', runId);
  assert.ok(!fs.existsSync(runtime) && !fs.existsSync(temporary));
  fs.mkdirSync(runtime); fs.mkdirSync(temporary);
  fs.writeFileSync(path.join(runtime, 'context.json'), JSON.stringify({ marker: 'intentionally-invalid-harness-marker', run_id: runId, compose_project: s.ctx.context.compose_project, api_port: 18000, frontend_port: 15173, owner_id: 'life-invalid-owner' }), 'utf8');
  try {
    const process = await processChild(['-CleanupRunId', runId], { timeoutMs: 60000 });
    return { run_id: runId, process: { code: process.code, timed_out: process.timed_out }, summary: readJson(path.join(artifactFor(runId), 'summary.json')), cleanup: readJson(path.join(artifactFor(runId), 'cleanup.json')) };
  } finally {
    // LIFE_009：仅删除刚创建且验证在runtime/tmp下的唯一无部署目录，拒绝链接目标。
    for (const [folder, target] of [['runtime', runtime], ['tmp', temporary]]) {
      assert.equal(target, ownedPath(folder, runId));
      if (fs.existsSync(target)) { assert.ok(!fs.lstatSync(target).isSymbolicLink()); fs.rmSync(target, { recursive: true }); }
    }
  }
}
