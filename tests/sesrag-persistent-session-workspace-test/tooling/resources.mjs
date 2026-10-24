import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { SUITE_ROOT } from './preflight.mjs';
import { runCommand, cleanChildEnvironment } from './process-registry.mjs';

export const RUN_ID = /^ws-[0-9]{8}t[0-9]{6}z-[a-f0-9]{8}$/;
export function runPath(kind, runId) {
  if (!['runtime', 'tmp', 'artifacts'].includes(kind) || !RUN_ID.test(runId ?? '')) throw new Error('非法运行路径或 run_id');
  const root = path.resolve(SUITE_ROOT, kind);
  const target = path.resolve(root, runId);
  for (const candidate of [root, target]) {
    if (fs.existsSync(candidate) && fs.lstatSync(candidate).isSymbolicLink()) throw new Error('拒绝符号链接运行路径');
  }
  if (path.dirname(target) !== root) throw new Error('运行路径越界');
  return target;
}
export function atomicJson(target, value) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const temporary = `${target}.${process.pid}.${crypto.randomUUID()}.tmp`;
  try {
    fs.writeFileSync(temporary, JSON.stringify(value, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
    fs.renameSync(temporary, target);
  } finally { fs.rmSync(temporary, { force: true }); }
}
export function assertOwnership(labels, session, project = null) {
  if (labels?.['io.sesrag.test.run_id'] !== session.run_id || labels?.['io.sesrag.test.owner'] !== session.owner_token
      || (project && labels?.['com.docker.compose.project'] !== project)) throw new Error('资源标签/归属不符，拒绝删除');
}
export function assertEngine(expected, actual) {
  if (!expected?.id || !expected?.context || !actual || expected.id !== actual.id || expected.context !== actual.context) throw new Error('Docker Engine/context 已变化，拒绝操作原账本资源');
}
export function cleanEnvironment(extra = {}) {
  return cleanChildEnvironment(extra);
}
export async function docker(args, options = {}) {
  const result = await runCommand('docker', args, { env: cleanEnvironment(), ...options, rawOutput: true });
  if (result.code !== 0 || result.timedOut || result.truncated) throw Object.assign(new Error(`Docker 命令失败（${result.timedOut ? '超时' : result.truncated ? '输出超限' : result.code}）：${result.output.slice(-4000)}`),
    { commandExitCode: result.code, timedOut: result.timedOut, truncated: result.truncated, signal: result.signal });
  return (options.combinedOutput ? result.output : result.stdout).trim();
}
export async function engineIdentity() {
  const info = JSON.parse(await docker(['info', '--format', '{{json .}}']));
  if (info.OSType !== 'linux') throw new Error('需要 Docker Linux Engine');
  return { id: info.ID, context: await docker(['context', 'show']), version: info.ServerVersion, cpus: info.NCPU, memory_bytes: info.MemTotal };
}
export async function snapshot() {
  const output = {};
  for (const [kind, args] of Object.entries({ containers: ['ps', '-aq'], networks: ['network', 'ls', '-q'], volumes: ['volume', 'ls', '-q'] })) output[kind] = (await docker(args)).split(/\r?\n/).filter(Boolean);
  return output;
}
export async function privateDirectory(directory) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  if (process.platform !== 'win32') { fs.chmodSync(directory, 0o700); return; }
  const sid = await runCommand('pwsh', ['-NoProfile', '-Command', '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value']);
  if (sid.code !== 0 || !/^S-\d+(?:-\d+)+$/.test(sid.output.trim())) throw new Error('无法确认 runtime ACL 用户 SID');
  const acl = await runCommand('icacls', [directory, '/inheritance:r', '/grant:r', `*${sid.output.trim()}:(OI)(CI)F`]);
  if (acl.code !== 0 || acl.timedOut) throw new Error('无法限制 runtime ACL');
}

// 启动先记意图；清理按标签补发现，覆盖构建/Compose 中途硬停窗口。
export async function cleanupResources(session, composeDown, adapters = {}) {
  const command = adapters.docker ?? docker;
  const identify = adapters.engineIdentity ?? engineIdentity;
  const takeSnapshot = adapters.snapshot ?? snapshot;
  const result = { schema_version: 1, run_id: session.run_id, owner_token: session.owner_token, engine: session.engine, projects: session.projects, actions: [], errors: [], residual: {}, retained: ['artifacts 脱敏历史报告', 'suite node_modules/.cache', 'Docker 基础镜像/共享构建缓存'] };
  assertEngine(session.engine, await identify());
  const specifications = [
    ['containers', ['ps', '-aq'], ['inspect'], ['rm', '-f', '-v']],
    ['networks', ['network', 'ls', '-q'], ['network', 'inspect'], ['network', 'rm']],
    ['volumes', ['volume', 'ls', '-q'], ['volume', 'inspect'], ['volume', 'rm']],
  ];
  const lines = (value) => value.split(/\r?\n/).filter(Boolean);
  const byProject = async (listArgs) => [...new Set((await Promise.all(session.projects.map(async (project) =>
    lines(await command([...listArgs, '--filter', `label=com.docker.compose.project=${project}`]))))).flat())];
  const scopedRun = async (listArgs) => adapters.projectOnly ? byProject(listArgs)
    : lines(await command([...listArgs, '--filter', `label=io.sesrag.test.run_id=${session.run_id}`]));
  const discover = async (listArgs) => [...new Set([
    ...await scopedRun(listArgs), ...await byProject(listArgs),
  ])];
  // Compose down 会按 project 广泛删除；先核验全部候选，不能先删再检查归属。
  let ownershipValid = true;
  for (const [, listArgs, inspectArgs] of specifications) {
    for (const id of await discover(listArgs)) {
      try {
        const item = JSON.parse(await command([...inspectArgs, id]))[0];
        const labels = item.Config?.Labels ?? item.Labels;
        assertOwnership(labels, session);
        if (!session.projects.includes(labels['com.docker.compose.project'])) throw new Error('资源 project 未登记');
      } catch (error) { ownershipValid = false; result.errors.push(error.message); }
    }
  }
  if (ownershipValid && composeDown) {
    try { await composeDown(); result.actions.push('Compose down --volumes --remove-orphans'); }
    catch (error) { result.errors.push(`Compose down：${error.message}`); }
  }
  for (const [kind, listArgs, inspectArgs, removeArgs] of specifications) {
    const ids = await discover(listArgs);
    for (const id of ids) {
      try {
        const item = JSON.parse(await command([...inspectArgs, id]))[0];
        const labels = item.Config?.Labels ?? item.Labels;
        assertOwnership(labels, session);
        if (!session.projects.includes(labels['com.docker.compose.project'])) throw new Error('资源 project 未登记');
        await command([...removeArgs, id]); result.actions.push(`${kind} 删除 ${id}`);
      } catch (e) { result.errors.push(e.message); }
    }
    // 残留以所有删除结束后的独立查询为准；不重复执行会随分类数增长的中间扫描。
  }
  result.residual.image_tags = [];
  for (const image of session.images ?? []) {
    if (!new RegExp(`^sesrag-ws-(app|frontend|tools):${session.run_id}$`).test(image.tag)) { ownershipValid = false; result.errors.push('镜像 tag 非本轮命名空间'); continue; }
    const found = await command(['image', 'ls', '--no-trunc', '--format', '{{.ID}}', image.tag]);
    if (!found) continue;
    if (!image.id || found !== image.id) {
      const item = JSON.parse(await command(['image', 'inspect', image.tag]))[0];
      try {
        if (image.id || item.Id !== found) throw new Error('镜像 tag 身份变化');
        const labels = item.Config?.Labels;
        if (!session.source_digest || labels?.['io.sesrag.test.suite'] !== 'workspace-test' || labels?.['io.sesrag.test.source'] !== session.source_digest) throw new Error('镜像缺少本轮来源标签');
        image.id = item.Id;
      } catch (error) { result.errors.push(`${image.tag}: ${error.message}`); result.residual.image_tags.push(image.tag); continue; }
    }
    try { await command(['image', 'rm', image.tag]); result.actions.push(`移除专用 tag ${image.tag}`); }
    catch (e) { result.errors.push(e.message); }
    if (await command(['image', 'ls', '-q', image.tag])) result.residual.image_tags.push(image.tag);
  }
  const after = await takeSnapshot();
  result.preexisting_missing = Object.fromEntries(Object.entries(session.before ?? {}).map(([kind, ids]) => [kind, ids.filter((id) => !after[kind].includes(id))]));
  // 删除结束后独立查询，不能把删除过程中的旧查询当作最终残留审计。
  assertEngine(session.engine, await identify());
  for (const [kind, listArgs] of specifications) {
    result.residual[kind] = await scopedRun(listArgs);
    result.residual[`${kind}_by_project`] = [...new Set((await Promise.all(session.projects.map(async (project) =>
      lines(await command([...listArgs, '--filter', `label=com.docker.compose.project=${project}`]))))).flat())];
  }
  result.status = ownershipValid && Object.values(result.residual).every((list) => list.length === 0) && Object.values(result.preexisting_missing).every((list) => list.length === 0) ? 'passed' : 'failed';
  // down 错误可被受约束的逐资源恢复消除，但保留原始错误，查询失败由调用方判 unknown。
  return result;
}
