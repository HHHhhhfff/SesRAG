import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { REPO_ROOT, SUITE_ROOT, buildSourceManifest, runPreflight, validateManifest } from './preflight.mjs';
import { writeRunReport, sanitizeText } from './report.mjs';
import { processIdentity, sameProcess, terminateRegistered, withProcessContext, runCommand } from './process-registry.mjs';
import { RUN_ID, cleanupResources, cleanEnvironment, assertEngine, docker, engineIdentity, privateDirectory, runPath, snapshot, atomicJson } from './resources.mjs';
import { runCompose, waitService, publishedPort } from './compose.mjs';
import { invokeCategoryProcess } from './category-runner.mjs';
import { runtimeInventory } from './runtime-inventory.mjs';
import { readCaseCatalog } from './case-catalog.mjs';

const timestamp = () => new Date().toISOString();
const token = (bytes = 32) => crypto.randomBytes(bytes).toString('base64url');
const makeRunId = () => `ws-${timestamp().replace(/[-:]/g, '').replace(/\.\d{3}/, '').toLowerCase()}-${crypto.randomBytes(4).toString('hex')}`;
const manifestPath = path.join(SUITE_ROOT, 'specific_test_script/manifest.json');
const bytesInGiB = 1024 ** 3;
const failure = (message, exitCode = 2) => Object.assign(new Error(message), { exitCode });
export const isExpectedToolExit = (error) => error.commandExitCode === 19 && !error.timedOut && !error.truncated && !error.signal;

export async function runStage(timeoutMs, action) {
  const deadline = Date.now() + timeoutMs;
  const result = await withProcessContext({ deadline }, action);
  if (Date.now() > deadline) throw failure('命令阶段总期限已到');
  return result;
}

export function parseOptions(args) {
  const out = { mode: 'Environment', categories: [], runId: null, holdSeconds: 0, purgeToolCache: false, frozenBuild: null };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--mode') out.mode = args[++i];
    else if (arg === '--categories') out.categories = String(args[++i] ?? '').split(',').map((x) => x.trim()).filter(Boolean);
    else if (arg === '--run-id') out.runId = args[++i];
    else if (arg === '--hold-seconds') out.holdSeconds = Number(args[++i]);
    else if (arg === '--frozen-build') out.frozenBuild = args[++i];
    else if (arg === '--purge-tool-cache') out.purgeToolCache = true;
    else throw failure(`未知参数：${arg}`);
  }
  if (!['Environment', 'Selected', 'All', 'Cleanup'].includes(out.mode)) throw failure('Mode 必须为 Environment、Selected、All 或 Cleanup');
  if (!Number.isInteger(out.holdSeconds) || out.holdSeconds < 0 || out.holdSeconds > 3600) throw failure('HoldSeconds 必须在0～3600之间');
  if (out.mode === 'Environment' && (out.runId || out.categories.length || out.frozenBuild || out.purgeToolCache)) throw failure('Environment 不接受 RunId/Categories/FrozenBuild/PurgeToolCache');
  if (out.mode === 'Selected' && (!out.categories.length || out.runId || out.holdSeconds || out.purgeToolCache)) throw failure('Selected 必须提供类别且不能提供 RunId/HoldSeconds/PurgeToolCache');
  if (out.mode === 'All' && (out.runId || out.categories.length || out.holdSeconds || out.purgeToolCache)) throw failure('All 不接受 RunId/Categories/HoldSeconds/PurgeToolCache');
  if (out.mode === 'Cleanup' && (!RUN_ID.test(out.runId ?? '') || out.categories.length || out.holdSeconds || out.frozenBuild)) throw failure('Cleanup 需要合法 RunId，且不接受其它运行参数');
  if (out.purgeToolCache) throw failure('本入口尚不支持 PurgeToolCache');
  return out;
}
function prepareArtifacts(root) {
  for (const child of ['', 'diagnostics', 'services', 'categories', 'browser']) fs.mkdirSync(path.join(root, child), { recursive: true });
}
function publish(file, value, session) {
  const clean = (item) => typeof item === 'string' ? sanitizeText(item, session.secret_values ?? [])
    : Array.isArray(item) ? item.map(clean) : item && typeof item === 'object' ? Object.fromEntries(Object.entries(item).map(([key, child]) => [key, clean(child)])) : item;
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, (typeof value === 'string' ? clean(value) : JSON.stringify(clean(value), null, 2)) + '\n', 'utf8');
}
function appendConsole(session, message) {
  fs.appendFileSync(path.join(runPath('artifacts', session.run_id), 'console.log'), sanitizeText(`[${timestamp()}] ${message}`, session.secret_values ?? []) + '\n', 'utf8');
}
function publicLedger(session) {
  return Object.fromEntries(['schema_version', 'run_id', 'mode', 'created_at', 'owner_token', 'engine', 'before', 'projects', 'images', 'tools', 'processes', 'main_process', 'source_digest', 'dependencies'].map((key) => [key, session[key]]));
}
function saveSession(session) {
  const runtime = runPath('runtime', session.run_id);
  if (!fs.existsSync(runtime)) return;
  atomicJson(path.join(runtime, 'session.json'), session);
  atomicJson(path.join(runtime, 'resource-ledger.json'), publicLedger(session));
  atomicJson(path.join(runPath('artifacts', session.run_id), 'recovery-ledger.json'), publicLedger(session));
}
function registerProcess(session, entry, active) {
  const existing = session.processes.find((item) => sameProcess(item, entry) || (item.unverified && entry.unverified && item.pid === entry.pid));
  if (existing) Object.assign(existing, entry, { active }); else session.processes.push({ ...entry, active });
  saveSession(session);
}
function isLive(pid) {
  if (!Number.isSafeInteger(pid) || pid <= 0) return false;
  try { process.kill(pid, 0); return true; } catch (error) { return error.code !== 'ESRCH'; }
}
export function assertInactive(identity) {
  if (!identity?.pid) return;
  const actual = processIdentity(identity.pid);
  if (sameProcess(identity, actual)) throw failure('该运行的主进程仍活跃，拒绝 Cleanup；请先停止运行', 3);
  if (!actual && isLive(identity.pid)) throw failure('主进程身份无法核验，拒绝清理活跃运行', 3);
}
function acquireLock(state) {
  fs.mkdirSync(path.dirname(state.lockFile), { recursive: true });
  if (fs.existsSync(state.lockFile)) {
    if (fs.lstatSync(state.lockFile).isSymbolicLink()) throw failure('运行锁不允许符号链接');
    const existing = JSON.parse(fs.readFileSync(state.lockFile, 'utf8'));
    if (!existing.main_process && isLive(existing.pid)) throw failure('旧锁进程仍活跃或无法核验，拒绝覆盖', 3);
    if (existing.main_process) assertInactive(existing.main_process);
    throw failure(`发现未完成运行 ${existing.run_id ?? '未知'}，请先使用 Cleanup 恢复清理`, 3);
  }
  const identity = processIdentity(process.pid);
  if (!identity?.created_at || !identity.executable) throw failure('无法获取运行器主进程身份');
  state.session.main_process = identity;
  fs.writeFileSync(state.lockFile, JSON.stringify({ run_id: state.session.run_id, pid: process.pid, started_at: timestamp(), main_process: identity }), { flag: 'wx', mode: 0o600 });
  state.ownsLock = true;
}
function releaseLock(state) {
  if (!state.ownsLock || !fs.existsSync(state.lockFile)) return;
  const lock = JSON.parse(fs.readFileSync(state.lockFile, 'utf8'));
  if (lock.run_id !== state.session.run_id) throw failure('运行锁归属已变化，拒绝删除');
  fs.rmSync(state.lockFile); state.ownsLock = false;
}
function createEnvironment(state) {
  const session = state.session;
  const pgPassword = token(); const modelKey = token(); const controlToken = token();
  const databaseUrl = `postgresql+psycopg://sesrag:${encodeURIComponent(pgPassword)}@postgres:5432/sesrag_workspace`;
  session.secret_values.push(pgPassword, databaseUrl, modelKey, controlToken);
  session.compose_env = {
    WS_TEST_REPO_ROOT: REPO_ROOT.replace(/\\/g, '/'), WS_TEST_TMP_DIR: state.temp.replace(/\\/g, '/'),
    WS_TEST_RUN_ID: session.run_id, WS_TEST_OWNER_TOKEN: session.owner_token, WS_TEST_PROJECT: `sesrag-ws-${session.run_id.slice(-8)}-build`, WS_TEST_CATEGORY: 'env',
    WS_TEST_SOURCE_DIGEST: session.source_digest,
    WS_TEST_APP_IMAGE: session.images[0].tag, WS_TEST_FRONTEND_IMAGE: session.images[1].tag, WS_TEST_TOOLS_IMAGE: session.images[2].tag,
    WS_TEST_POSTGRES_DB: 'sesrag_workspace', WS_TEST_POSTGRES_USER: 'sesrag', WS_TEST_POSTGRES_PASSWORD: pgPassword,
    WS_TEST_DATABASE_URL: databaseUrl, WS_TEST_REDIS_URL: 'redis://redis:6379/0', WS_TEST_MODEL_API_KEY: modelKey,
    WS_TEST_PROVIDER_CONTROL_TOKEN: controlToken, WS_TEST_API_PORT: '0', WS_TEST_FRONTEND_PORT: '0', WS_TEST_PROVIDER_CONTROL_PORT: '0',
  };
  fs.writeFileSync(path.join(state.runtime, 'secrets.json'), JSON.stringify({ pgPassword, databaseUrl, modelKey, controlToken }), { flag: 'wx', mode: 0o600 });
  writeComposeEnvironment(session);
}
function writeComposeEnvironment(session) {
  fs.writeFileSync(path.join(runPath('runtime', session.run_id), 'compose.env'), Object.entries(session.compose_env).map(([key, value]) => `${key}=${value}`).join('\n') + '\n', { encoding: 'utf8', mode: 0o600 });
}
async function initializeRun(state) {
  acquireLock(state); await privateDirectory(state.runtime); fs.mkdirSync(state.temp, { recursive: true });
  state.session.source_before = buildSourceManifest(); state.session.source_digest = state.session.source_before.source_digest;
  createEnvironment(state); saveSession(state.session);
  const disk = fs.statfsSync(SUITE_ROOT, { bigint: true }); const availableDisk = Number(disk.bavail * disk.bsize);
  if (availableDisk < 15 * bytesInGiB) throw failure('suite 所在磁盘可用空间少于 15 GiB', 3);
  state.session.host = { platform: process.platform, node: process.versions.node, arch: process.arch, free_memory_bytes: os.freemem(), available_disk_bytes: availableDisk };
  process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(SUITE_ROOT, '.cache/ms-playwright');
  let preflight;
  try { preflight = await runPreflight({ browserSelfTest: true }); } catch (error) { throw failure(`本机工具前提不满足：${error.message}`, 3); }
  publish(path.join(state.artifacts, 'diagnostics/preflight.json'), preflight, state.session);
  try { state.session.engine = await engineIdentity(); state.session.before = await snapshot(); }
  catch (error) { throw failure(`Docker 环境前提不满足：${error.message}`, 3); }
  if (state.session.engine.cpus < 2 || state.session.engine.memory_bytes < 4 * bytesInGiB) throw failure('Docker Engine 资源不足以运行测试环境', 3);
  saveSession(state.session);
}
async function buildImages(session) {
  const project = `sesrag-ws-${session.run_id.slice(-8)}-build`;
  session.projects.push(project); session.resources_started = true; saveSession(session);
  for (const service of ['api', 'frontend', 'tools']) {
    appendConsole(session, `构建专用镜像：${service}`);
    const result = await runCompose(session, project, ['build', service], { timeoutMs: 1800000, combinedOutput: true });
    fs.appendFileSync(path.join(runPath('artifacts', session.run_id), 'build.log'), sanitizeText(result, session.secret_values) + '\n', 'utf8');
    const image = session.images.find((item) => item.name === (service === 'api' ? 'app' : service));
    image.id = await docker(['image', 'inspect', '--format', '{{.Id}}', image.tag]); saveSession(session);
  }
}
async function setupProject(session, project, category, hooks) {
  session.projects.push(project); session.compose_env.WS_TEST_PROJECT = project; session.compose_env.WS_TEST_CATEGORY = category;
  session.compose_env.WS_TEST_RETRY_BASE_DELAY = category === 'workspace' ? '15' : '2';
  writeComposeEnvironment(session); saveSession(session);
  await runCompose(session, project, ['up', '-d', '--no-build', 'postgres', 'redis', 'provider'], { timeoutMs: 120000 });
  const [pg] = await Promise.all(['postgres', 'redis', 'provider'].map((service) => waitService(session, project, service, 'healthy')));
  await verifyContainer(session, project, pg); session.endpoints.pg_container = pg;
  await hooks.afterBaseServices?.(session, project);
  session.endpoints.provider_control_url = `http://127.0.0.1:${await publishedPort(session, project, 'provider', 8081)}`; saveSession(session);
  for (const service of ['migrate', 'profile-init']) {
    await runCompose(session, project, ['up', '-d', '--no-build', service], { timeoutMs: 60000 });
    const result = await waitService(session, project, service, 'exited');
    if (result.exit_code !== 0) throw failure(`${service} 正式初始化失败，退出码 ${result.exit_code}`);
  }
  await runCompose(session, project, ['up', '-d', '--no-build', 'api', 'worker', 'frontend'], { timeoutMs: 60000 });
  await Promise.all(['api', 'worker', 'frontend'].map((service) => waitService(session, project, service, 'healthy')));
  session.endpoints.api_base_url = `http://127.0.0.1:${await publishedPort(session, project, 'api', 8000)}`;
  session.endpoints.frontend_base_url = `http://127.0.0.1:${await publishedPort(session, project, 'frontend', 5173)}`; saveSession(session);
}
async function verifyContainer(session, project, id) {
  const labels = JSON.parse(await docker(['inspect', id]))[0].Config?.Labels;
  if (labels?.['io.sesrag.test.run_id'] !== session.run_id || labels?.['io.sesrag.test.owner'] !== session.owner_token || labels?.['com.docker.compose.project'] !== project) throw failure('容器身份不符，拒绝使用');
}
export async function runTools(session, project, args, timeoutMs = 120000) {
  const name = `${project}-tools-${crypto.randomBytes(6).toString('hex')}`;
  const intent = { name, project, intent_at: timestamp() };
  session.tools.push(intent); saveSession(session);
  fs.appendFileSync(path.join(runPath('runtime', session.run_id), 'resource-intents.jsonl'), JSON.stringify(intent) + '\n', { mode: 0o600 });
  return runCompose(session, project, ['--profile', 'tools', 'run', '--rm', '--no-deps', '--name', name,
    '--label', `io.sesrag.test.run_id=${session.run_id}`, '--label', `io.sesrag.test.owner=${session.owner_token}`, 'tools', ...args], { timeoutMs });
}
function parsePassed(text, label) {
  let result; try { result = JSON.parse(text); } catch { throw failure(`${label} 未返回合法 JSON`); }
  if (result.status !== 'passed') throw failure(`${label} 未通过`); return result;
}
async function verifyProbeDatabase(session, project) {
  const id = session.endpoints.pg_container; await verifyContainer(session, project, id);
  const server = await docker(['exec', id, 'psql', '-U', 'sesrag', '-d', 'sesrag_workspace', '-Atc', 'SELECT system_identifier FROM pg_control_system()']);
  if (!/^\d+$/.test(server)) throw failure('无法核验测试 PostgreSQL system_identifier');
  const name = `sesrag_session_probe_${session.run_id.slice(-8)}`; session.probe_database = { name, server_id: server, project }; saveSession(session);
  const output = await runTools(session, project, ['/suite/tooling/db-admin.py', 'self-test', '--expected-server-id', server, '--expected-namespace', project]);
  parsePassed(output, 'PostgreSQL 专库工具自测'); publish(path.join(runPath('artifacts', session.run_id), 'diagnostics/probe-database.json'), output, session);
}
async function runEnvironment(state, options, hooks) {
  const session = state.session; const project = `sesrag-ws-${session.run_id.slice(-8)}-env`;
  await runStage(1800000, () => buildImages(session));
  await runStage(300000, () => setupProject(session, project, 'env', hooks));
  publish(path.join(state.artifacts, 'diagnostics/runtime-inventory.json'), await runtimeInventory(session, project), session);
  const toolsTest = await runTools(session, project, ['-m', 'pytest', '-q', '/suite/tooling/test_environment_tools.py', '--junitxml=/outputs/python-tools.xml']);
  publish(path.join(state.artifacts, 'diagnostics/python-tools.log'), toolsTest, session);
  const junit = path.join(state.temp, 'python-tools.xml'); if (!fs.existsSync(junit)) throw failure('Python 工具自测未写出 JUnit');
  publish(path.join(state.artifacts, 'diagnostics/python-tools.xml'), fs.readFileSync(junit, 'utf8'), session);
  await runTools(session, project, ['/suite/tooling/prepare-fixtures.py', '--output', '/outputs/inputs', '--manifest', '/outputs/fixture-manifest.json']);
  const fixture = path.join(state.temp, 'fixture-manifest.json'); if (!fs.existsSync(fixture)) throw failure('fixture 工具未写出 manifest');
  publish(path.join(state.artifacts, 'diagnostics/fixture-manifest.json'), JSON.parse(fs.readFileSync(fixture, 'utf8')), session);
  const probe = await runTools(session, project, ['/suite/tooling/environment_probe.py', '--json']);
  parsePassed(probe, '环境技术探测'); publish(path.join(state.artifacts, 'diagnostics/environment-probe.json'), probe, session);
  const provider = await runTools(session, project, ['/suite/tooling/provider-selftest.py', '--base-url', 'http://provider:8080', '--control-url', 'http://provider:8081'], 60000);
  parsePassed(provider, '受控 Provider 协议自测'); publish(path.join(state.artifacts, 'diagnostics/provider-selftest.json'), provider, session);
  await verifyProbeDatabase(session, project);
  if (options.holdSeconds) { appendConsole(session, `观察窗口开始：${options.holdSeconds} 秒`); await delay(options.holdSeconds * 1000, undefined, { signal: state.controller.signal }); }
}
async function collectEvidence(state) {
  for (const project of state.session.projects) {
    const result = await runCompose(state.session, project, ['logs', '--no-color', '--timestamps', '--tail', '1000'], { timeoutMs: 120000 });
    publish(path.join(state.artifacts, `services/${project}.log`), result, state.session);
  }
  const after = buildSourceManifest(); state.session.source_unchanged = state.session.source_before ? after.source_digest === state.session.source_before.source_digest : null;
  publish(path.join(state.artifacts, 'diagnostics/source-manifest.json'), { before: state.session.source_before, after, unchanged: state.session.source_unchanged }, state.session);
  const walk = (directory) => {
    for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw failure('artifact含符号链接，拒绝发布越界证据');
      if (item.isDirectory()) { walk(target); continue; }
      if (!/\.(json|jsonl|txt|log|xml|md|html|csv)$/i.test(item.name)) continue;
      if (fs.statSync(target).size > 10 * 1024 * 1024) throw failure('文本证据超过发布上限');
      const text = fs.readFileSync(target, 'utf8');
      if (item.name.endsWith('.json')) {
        let parsed; try { parsed = JSON.parse(text); } catch { publish(target, text, state.session); continue; }
        publish(target, parsed, state.session);
      } else publish(target, text, state.session);
    }
  };
  walk(state.artifacts);
  if (state.session.source_unchanged === false) throw failure('运行期源码发生变化，本轮不能证明同源环境');
}
async function cleanupState(state) {
  const session = state.session; const processErrors = []; const actions = [];
  const helperProcesses = path.join(state.runtime, 'helper-processes.json');
  if (fs.existsSync(helperProcesses)) for (const entry of JSON.parse(fs.readFileSync(helperProcesses, 'utf8'))) {
    if (!session.processes.some((item) => sameProcess(item, entry))) session.processes.push(entry);
  }
  for (const entry of session.processes.filter((item) => item.active)) {
    try { actions.push(`进程 ${entry.pid}：${terminateRegistered(entry)}`); entry.active = false; } catch (error) { processErrors.push(error.message); }
  }
  let result = { schema_version: 1, run_id: session.run_id, status: 'passed', residual: {}, actions: [], errors: [] };
  if (session.resources_started) result = await cleanupResources(session, async () => {
    if (!fs.existsSync(path.join(state.runtime, 'compose.env'))) throw failure('私有 Compose 配置缺失，改用已核验资源逐项清理');
    for (const project of session.projects) await runCompose(session, project, ['down', '--volumes', '--remove-orphans', '--timeout', '30'], { timeoutMs: 60000 });
  });
  result.actions.push(...actions); result.errors.push(...processErrors); result.residual.processes = session.processes.filter((item) => item.active).map((item) => item.pid);
  if (processErrors.length) result.status = 'failed'; result.ledger = publicLedger(session);
  // Docker 与进程审计通过后才移除凭据，失败时保留恢复所需的私有账本。
  if (result.status === 'passed') for (const directory of [state.temp, state.runtime]) fs.rmSync(directory, { recursive: true, force: true });
  result.residual.runtime = fs.existsSync(state.runtime) ? ['runtime'] : []; result.residual.tmp = fs.existsSync(state.temp) ? ['tmp'] : [];
  return result;
}
export function coveragePlan(options, manifest, suiteRoot = SUITE_ROOT) {
  validateManifest(manifest, suiteRoot);
  const selected = options.mode === 'All' ? manifest.categories.filter((item) => item.required).map((item) => item.category) : options.categories;
  if (new Set(selected).size !== selected.length || selected.some((id) => !manifest.categories.some((item) => item.category === id))) throw failure('Selected 分类重复或未知');
  const unready = manifest.categories.filter((item) => selected.includes(item.category) && item.status !== 'ready').map((item) => item.category);
  const catalog = readCaseCatalog(suiteRoot);
  return { selected, unready, expected_case_count: selected.reduce((sum, id) => sum + catalog.categories[id].length, 0), reason: unready.length ? `分类尚未 ready：${unready.join(', ')}` : null };
}

function categoryContext(state, entry, project) {
  const session = state.session;
  return { schema_version: 1, run_id: session.run_id, environment_id: project, category: entry.category,
    ...Object.fromEntries(['api_base_url', 'frontend_base_url', 'provider_control_url'].map((key) => [key, session.endpoints[key]])),
    artifact_dir: `artifacts/${session.run_id}/categories/${entry.category}/`, tmp_dir: `tmp/${session.run_id}/${entry.category}/`,
    fixture_version: JSON.parse(fs.readFileSync(path.join(SUITE_ROOT, 'fixtures/baseline.json'), 'utf8')).fixture_version,
    resource_helper: 'tooling/orchestrator.mjs', expected_case_ids: entry.case_ids };
}
export function validateContext(context) {
  const ajv = new Ajv2020({ allErrors: true }); addFormats(ajv);
  const validate = ajv.compile(JSON.parse(fs.readFileSync(path.join(SUITE_ROOT, 'schemas/run-context.schema.json'), 'utf8')));
  if (!validate(context)) throw failure(`分类上下文不符合 Schema：${JSON.stringify(validate.errors)}`);
  const prefix = `${context.run_id}/${context.category}/`;
  if (context.artifact_dir !== `artifacts/${context.run_id}/categories/${context.category}/` || context.tmp_dir !== `tmp/${prefix}`) throw failure('分类上下文目录与身份不符');
  return context;
}
async function freezeBuild(session, options, hooks) {
  if (options.frozenBuild) {
    session.resources_started = true; session.projects.push(`sesrag-ws-${session.run_id.slice(-8)}-build`); saveSession(session);
    const module = hooks.loadFrozenBuild ? null : await import('./frozen-builds.mjs');
    const loaded = await (hooks.loadFrozenBuild ?? module.loadFrozenBuild)(session, options.frozenBuild, { docker });
    session.frozen_build = loaded?.fingerprint ?? options.frozenBuild;
  } else {
    await (hooks.buildImages ?? buildImages)(session);
    if (!hooks.saveFrozenBuild) {
      const output = await runTools(session, `sesrag-ws-${session.run_id.slice(-8)}-build`, ['-c',
        "import importlib.metadata,json,sys;print(json.dumps({'python_version':sys.version.split()[0],'packages':sorted([{'name':p.metadata['Name'],'version':p.version} for p in importlib.metadata.distributions()],key=lambda p:p['name'].lower())}))"]);
      session.dependencies = { ...JSON.parse(output), node_version: process.versions.node };
    }
    const module = hooks.saveFrozenBuild ? null : await import('./frozen-builds.mjs');
    const saved = await (hooks.saveFrozenBuild ?? module.saveFrozenBuild)(session, { docker });
    session.frozen_build = typeof saved === 'string' ? saved : saved?.fingerprint;
    if (!session.frozen_build) throw failure('冻结构建未返回有效指纹');
  }
  saveSession(session);
}
async function cleanupProject(session, project, category, state) {
  const result = await cleanupResources({ ...session, projects: [project], images: [] }, () =>
    runCompose(session, project, ['down', '--volumes', '--remove-orphans', '--timeout', '30'], { timeoutMs: 60000 }), { projectOnly: true });
  publish(path.join(state.artifacts, `categories/${category}/cleanup.json`), result, session);
  return result;
}
// QLT_005由总入口在finally结束后结算；分类侧不能提前宣布容器已销毁。
async function lifecycleFaultDrills(state) {
  const session = state.session; const results = [];
  // QLT_005：两个全新环境真实运行失败/超时的分类子进程，验证同一个外层finally。
  for (const kind of ['exit', 'timeout']) {
    const category = `quality-${kind}`; const project = `sesrag-ws-${session.run_id.slice(-8)}-${category}`;
    const observed = { kind, project, status: 'failed' }; let deployed = false;
    fs.mkdirSync(path.join(state.artifacts, 'categories', category), { recursive: true });
    try {
      deployed = true; await setupProject(session, project, category, {});
      const response = await fetch(session.endpoints.api_base_url + '/health/ready', { signal: AbortSignal.timeout(10000) });
      const health = await response.json();
      if (!response.ok || health.database !== 'ready' || health.worker_count < 1) throw failure('异常闭环环境未真实就绪');
      observed.health = health;
      const child = await runCommand(process.execPath, ['-e', kind === 'exit'
        ? "console.log('QLT_005：主动分类失败');process.exit(19)"
        : "console.log('QLT_005：主动分类超时');setInterval(()=>{},1000)"], { timeoutMs: kind === 'exit' ? 15000 : 3000 });
      observed.child = { exit_code: child.code, timed_out: child.timedOut, truncated: child.truncated };
      if (child.truncated || (kind === 'exit' ? child.code !== 19 || child.timedOut : !child.timedOut)) throw failure('异常分类未到达预期退出分支');
      // 故意进入catch，再由finally采证清理；不是把子命令失败吞掉后宣称已清理。
      throw failure(`EXPECTED_CLASSIFICATION_${kind.toUpperCase()}`);
    } catch (error) {
      observed.expected_error_caught = error.message === `EXPECTED_CLASSIFICATION_${kind.toUpperCase()}`;
      observed.reason = sanitizeText(error.message, session.secret_values);
    } finally {
      if (deployed) {
        try {
          publish(path.join(state.artifacts, `categories/${category}/services.log`), await runCompose(session, project, ['logs', '--no-color', '--tail', '100']), session);
          observed.cleanup = await cleanupProject(session, project, category, state);
          observed.status = observed.expected_error_caught && observed.cleanup.status === 'passed' ? 'passed' : 'failed';
        } catch (error) { observed.reason = sanitizeText(error.message, session.secret_values); }
      }
      results.push(observed);
    }
    if (observed.cleanup?.status !== 'passed') break;
  }
  publish(path.join(state.artifacts, 'categories/quality/lifecycle-fault-drills.json'), { status: results.length === 2 && results.every((item) => item.status === 'passed') ? 'passed' : 'failed', results }, session);
}
export function finalizeLifecycleCase(state, cleanup) {
  const file = path.join(state.artifacts, 'categories/quality/result.json');
  if (!fs.existsSync(file)) return;
  const readEvidence = (target) => { try { return JSON.parse(fs.readFileSync(target, 'utf8')); } catch { return null; } };
  const report = readEvidence(file);
  if (!Array.isArray(report?.cases)) {
    if (state.session.category_counts) state.session.category_counts.harness_error = (state.session.category_counts.harness_error ?? 0) + 1;
    (state.session.category_reasons ??= []).push('quality最终报告缺失/损坏，不能完成生命周期结算'); return;
  }
  const item = report.cases.find((entry) => entry.case_id === 'QLT_005');
  if (!item || item.reason_code !== 'AWAITING_OUTER_CLEANUP') return;
  const previous = item.status;
  const categoryCleanup = readEvidence(path.join(state.artifacts, 'categories/quality/cleanup.json'));
  const drillFile = path.join(state.artifacts, 'categories/quality/lifecycle-fault-drills.json');
  const drills = readEvidence(drillFile);
  const evidenceFile = path.join(state.artifacts, 'categories/quality/QLT_005.json'); const observed = readEvidence(evidenceFile);
  const passed = !!observed && cleanup.status === 'passed' && categoryCleanup?.status === 'passed' && drills?.status === 'passed' && state.session.source_unchanged === true;
  item.status = passed ? 'passed' : 'failed';
  item.actual = passed ? '正常分类、全新环境分类主动失败、全新环境分类超时三条路径均采证并在finally清理；分类及全轮独立审计通过，容器/网络/卷/专有tag/runtime/tmp无残留，源码未变。' : '正常/异常闭环、独立残留审计或源码一致性未满足要求，见cleanup及故障演练证据。';
  item.reason_code = passed ? null : 'LIFECYCLE_FINAL_AUDIT_FAILED'; item.reason = passed ? null : item.actual;
  if (categoryCleanup) item.evidence_paths.push('categories/quality/cleanup.json');
  if (drills) { item.evidence_paths.push('categories/quality/lifecycle-fault-drills.json'); report.evidence.push('categories/quality/lifecycle-fault-drills.json'); }
  publish(evidenceFile, { ...(observed ?? { case_id: 'QLT_005', missing_original_observation: true }), outer_finalization: { status: item.status, actual: item.actual, cleanup_status: cleanup.status, residual: cleanup.residual } }, state.session);
  report.status = report.cases.some((entry) => entry.status === 'failed') ? 'failed' : report.cases.some((entry) => entry.status !== 'passed') ? 'blocked' : 'passed';
  report.finished_at = timestamp(); if (categoryCleanup) report.evidence.push('categories/quality/cleanup.json'); publish(file, report, state.session);
  if (state.session.category_counts) { state.session.category_counts[previous] -= 1; state.session.category_counts[item.status] += 1; }
}
export async function runCategories(state, options, hooks, manifest) {
  const session = state.session; const selected = options.mode === 'All' ? manifest.categories.filter((entry) => entry.required).map((entry) => entry.category) : options.categories;
  const counts = { passed: 0, failed: 0, blocked: 0, not_run: 0, harness_error: 0 }; session.category_counts = counts; session.category_reasons = [];
  await runStage(1800000, () => freezeBuild(session, options, hooks)); const totalDeadline = Date.now() + 7200000; let stop = false;
  for (const category of selected) {
    const entry = manifest.categories.find((item) => item.category === category);
    if (stop || state.controller.signal.aborted || Date.now() >= totalDeadline) { counts.not_run += entry.case_ids.length; session.category_reasons.push(`${category} 未执行：上一分类清理失败、中断或总期限已到`); continue; }
    const project = `sesrag-ws-${session.run_id.slice(-8)}-${category}`; let deployed = false; let categoryError;
    const artifactDir = path.join(state.artifacts, 'categories', category); fs.mkdirSync(artifactDir, { recursive: true });
    try {
      session.active_category = category; session.active_project = project; saveSession(session); deployed = true;
      await withProcessContext({ signal: state.controller.signal, secrets: session.secret_values,
        onProcess: (entry, active) => registerProcess(session, entry, active), deadline: Math.min(totalDeadline, Date.now() + 300000) }, () =>
        (hooks.setupProject ?? setupProject)(session, project, category, hooks));
      await (hooks.prepareCategoryFixtures ?? (async () => {
        await runTools(session, project, ['/suite/tooling/prepare-fixtures.py', '--output', `/outputs/${category}/inputs`, '--manifest', `/outputs/${category}/fixture-manifest.json`]);
        const fixture = path.join(state.temp, category, 'fixture-manifest.json');
        if (!fs.existsSync(fixture)) throw failure('分类fixture未生成manifest');
        publish(path.join(artifactDir, 'fixture-manifest.json'), JSON.parse(fs.readFileSync(fixture, 'utf8')), session);
      }))();
      const context = validateContext(categoryContext(state, entry, project));
      const contextDir = path.join(state.runtime, category); fs.mkdirSync(contextDir, { recursive: true });
      const contextPath = path.join(contextDir, 'context.json'); atomicJson(contextPath, context);
      fs.mkdirSync(path.join(state.temp, category), { recursive: true });
      publish(path.join(artifactDir, 'context.public.json'), context, session);
      const script = path.resolve(hooks.suiteRoot ?? SUITE_ROOT, entry.script);
      const args = script.endsWith('.mjs') ? [script, '--context', contextPath] : ['-NoProfile', '-File', script, '-ContextPath', contextPath];
      const result = await invokeCategoryProcess({ command: script.endsWith('.mjs') ? process.execPath : 'pwsh', args, cwd: SUITE_ROOT,
        resultPath: path.join(artifactDir, 'result.json'), artifactRoot: state.artifacts, context,
        timeoutMs: Math.min(entry.timeout_seconds * 1000, totalDeadline - Date.now()), logPath: path.join(artifactDir, 'console.log'),
        env: cleanEnvironment({ PLAYWRIGHT_BROWSERS_PATH: path.join(SUITE_ROOT, '.cache/ms-playwright'),
          PROVIDER_CONTROL_TOKEN: session.compose_env?.WS_TEST_PROVIDER_CONTROL_TOKEN ?? '', MODEL_API_KEY: session.compose_env?.WS_TEST_MODEL_API_KEY ?? '',
          WS_EVIDENCE_SECRETS: JSON.stringify(session.secret_values) }) });
      for (const item of result.result.cases) counts[item.status] += 1;
      // 分类输出必须脱敏后才发布到最终报告目录。
      publish(path.join(artifactDir, 'result.json'), result.result, session);
      // 工具安装不等于质量验收：仅使用当轮已核验的两项质量用例事实解除前置门禁。
      if (category === 'quality') session.quality_prerequisites = ['QLT_002', 'QLT_003'].every((id) =>
        result.result.cases.some((item) => item.case_id === id && item.status === 'passed')) ? 'ready' : 'blocked';
    } catch (error) {
      categoryError = error; counts.harness_error += 1; counts.not_run += entry.case_ids.length;
      session.category_reasons.push(`${category}：${sanitizeText(error.message, session.secret_values)}`);
      publish(path.join(artifactDir, 'harness-error.json'), { status: 'harness_error', reason: error.message }, session);
    } finally {
      if (deployed) {
        try {
          await withProcessContext({ secrets: session.secret_values, deadline: Date.now() + 120000,
            onProcess: (entry, active) => registerProcess(session, entry, active) }, async () => {
            if (hooks.collectProjectEvidence) return hooks.collectProjectEvidence(session, project, category, state);
            const logs = await runCompose(session, project, ['logs', '--no-color', '--timestamps', '--tail', '1000'], { timeoutMs: 120000 });
            publish(path.join(artifactDir, 'services.log'), logs, session);
          });
        } catch (error) { counts.harness_error += 1; session.category_reasons.push(`${category} 采证失败：${error.message}`); }
        try {
          const result = await withProcessContext({ secrets: session.secret_values, deadline: Date.now() + 180000,
            onProcess: (entry, active) => registerProcess(session, entry, active) }, () => (hooks.cleanupProject ?? cleanupProject)(session, project, category, state));
          if (result.status !== 'passed') { stop = true; counts.harness_error += 1; session.category_reasons.push(`${category} 子环境清理未通过`); }
        } catch (error) { stop = true; counts.harness_error += 1; session.category_reasons.push(`${category} 清理失败：${error.message}`); }
      }
      session.active_category = null; session.active_project = null; saveSession(session);
    }
    if (categoryError?.exitCode === 130 || state.controller.signal.aborted) stop = true;
  }
  const qualityFile = path.join(state.artifacts, 'categories/quality/result.json');
  if (!stop && fs.existsSync(qualityFile) && JSON.parse(fs.readFileSync(qualityFile, 'utf8')).cases.some((item) => item.case_id === 'QLT_005' && item.reason_code === 'AWAITING_OUTER_CLEANUP')) {
    await runStage(1200000, () => lifecycleFaultDrills(state));
  }
  return counts.harness_error ? 2 : counts.failed ? 1 : counts.blocked || counts.not_run ? 3 : 0;
}
export async function mainRun(options, hooks = {}) {
  const run = makeRunId();
  const state = { runtime: runPath('runtime', run), temp: runPath('tmp', run), artifacts: runPath('artifacts', run), lockFile: path.join(SUITE_ROOT, 'runtime/active.lock'),
    ownsLock: false, controller: new AbortController(), session: { schema_version: 1, run_id: run, mode: options.mode, owner_token: token(18), created_at: timestamp(), engine: null, before: {},
      projects: [], images: ['app', 'frontend', 'tools'].map((name) => ({ name, tag: `sesrag-ws-${name}:${run}`, id: null })),
      processes: [], tools: [], secret_values: [], endpoints: {}, statuses: [], resources_started: false } };
  prepareArtifacts(state.artifacts); const session = state.session;
  let manifest;
  if (options.mode !== 'Environment') {
    let coverage;
    try { manifest = hooks.manifest ?? JSON.parse(fs.readFileSync(manifestPath, 'utf8')); coverage = coveragePlan(options, manifest, hooks.suiteRoot ?? SUITE_ROOT); }
    catch (error) {
      return writeRunReport({ run_id: run, mode: options.mode, started_at: session.created_at, finished_at: timestamp(), cleanup_status: 'not_required',
        environment_status: 'not_run', counts: { harness_error: 1 }, original_exit_code: 2, not_run_reasons: [sanitizeText(error.message)] }, state.artifacts).final_exit_code;
    }
    publish(path.join(state.artifacts, 'coverage.json'), coverage, session);
    if (coverage.unready.length) {
      const report = writeRunReport({ run_id: run, mode: options.mode, started_at: session.created_at, finished_at: timestamp(), cleanup_status: 'not_required', environment_status: 'not_run',
      selected_categories: coverage.selected, required_categories: manifest.categories.filter((entry) => entry.required).map((entry) => entry.category), unready_categories: coverage.unready,
      counts: { not_run: coverage.expected_case_count },
      original_exit_code: 3, not_run_reasons: [coverage.reason] }, state.artifacts);
      process.stdout.write(`运行 ID：${run}\n报告：artifacts/${run}/summary.md\n${coverage.reason}\n`); return report.final_exit_code;
    }
  }
  let caught; let originalExit = 0; let environmentStatus = 'blocked'; let cleanup;
  const interrupt = () => state.controller.abort(); process.once('SIGINT', interrupt); process.once('SIGTERM', interrupt);
  const context = { signal: state.controller.signal, onProcess: (entry, active) => registerProcess(session, entry, active), secrets: session.secret_values };
  try {
    await withProcessContext(context, async () => {
      await (hooks.initialize ?? initializeRun)(state); appendConsole(session, `开始 ${options.mode} 运行：${run}`);
      if (options.mode === 'Environment') await (hooks.runEnvironment ?? runEnvironment)(state, options, hooks);
      else originalExit = await runCategories(state, options, hooks, manifest);
      environmentStatus = 'passed';
    });
  } catch (error) {
    caught = error; originalExit = state.controller.signal.aborted ? 130 : (error.exitCode ?? 2); environmentStatus = originalExit === 3 ? 'blocked' : 'failed';
    if (session.category_counts && Object.values(session.category_counts).every((count) => count === 0)) {
      session.category_counts.harness_error = 1;
      session.category_counts.not_run = (options.mode === 'All' ? manifest.categories : manifest.categories.filter((item) => options.categories.includes(item.category))).reduce((sum, item) => sum + item.case_ids.length, 0);
    }
    publish(path.join(state.artifacts, 'failure.txt'), error.message, session);
  } finally {
    // 中断停止后续部署，诊断和清理使用独立有界命令。
    await withProcessContext({ ...context, signal: undefined }, async () => {
      try { await withProcessContext({ ...context, signal: undefined, deadline: Date.now() + 120000 }, () => (hooks.collectEvidence ?? collectEvidence)(state)); }
      catch (error) { caught ??= error; if (!originalExit) originalExit = 2; environmentStatus = 'failed';
        try { publish(path.join(state.artifacts, 'diagnostics/collection-error.txt'), error.message, session); } catch { /* 采证目录不可写时仍必须继续清理。 */ } }
      try { cleanup = await withProcessContext({ ...context, signal: undefined, deadline: Date.now() + Math.min(1200000, 180000 + session.projects.length * 45000) }, () => (hooks.cleanup ?? cleanupState)(state)); }
      catch (error) { cleanup = { schema_version: 1, run_id: run, status: 'unknown', errors: [error.message], ledger: publicLedger(session), residual: { runtime: fs.existsSync(state.runtime) ? ['runtime'] : [], tmp: fs.existsSync(state.temp) ? ['tmp'] : [] } }; }
      // 清理失败/未知时保留恢复锁，下一次部署必须先经 Cleanup 核验遗留资源。
      if (['passed', 'not_required'].includes(cleanup.status)) {
        try { releaseLock(state); } catch (error) { cleanup.status = 'failed'; cleanup.errors.push(error.message); }
      }
    });
    process.removeListener('SIGINT', interrupt); process.removeListener('SIGTERM', interrupt);
  }
  publish(path.join(state.artifacts, 'cleanup.json'), cleanup, session);
  finalizeLifecycleCase(state, cleanup);
  if (session.category_counts && !session.category_counts.harness_error && !session.category_counts.failed && !session.category_counts.blocked && !session.category_counts.not_run && originalExit === 3) originalExit = 0;
  const summary = writeRunReport({ run_id: run, mode: options.mode, started_at: session.created_at, finished_at: timestamp(), environment_status: environmentStatus,
    cleanup_status: cleanup.status, source_unchanged: session.source_unchanged ?? null, original_exit_code: originalExit,
    counts: session.category_counts ?? { harness_error: originalExit === 2 ? 1 : 0 }, interrupted: state.controller.signal.aborted,
    selected_categories: options.mode === 'Environment' ? [] : options.mode === 'All' ? manifest.categories.filter((entry) => entry.required).map((entry) => entry.category) : options.categories,
    required_categories: manifest?.categories.filter((entry) => entry.required).map((entry) => entry.category) ?? [], frozen_build: session.frozen_build ?? null,
    quality_prerequisites: session.quality_prerequisites ?? 'pending',
    not_run_reasons: [...(caught ? [sanitizeText(caught.message, session.secret_values)] : []), ...(session.category_reasons ?? [])] }, state.artifacts);
  process.stdout.write(`运行 ID：${run}\n报告：artifacts/${run}/summary.md\n环境：${summary.environment_status}；产品验收：${summary.product_acceptance}；清理：${cleanup.status}\n`);
  return summary.final_exit_code;
}
export async function cleanupMode(options) {
  const runtime = runPath('runtime', options.runId); const artifact = runPath('artifacts', options.runId); const sessionFile = path.join(runtime, 'session.json'); const priorFile = path.join(artifact, 'cleanup.json');
  const recoveryFile = path.join(artifact, 'recovery-ledger.json');
  if (!fs.existsSync(sessionFile) && !fs.existsSync(priorFile) && !fs.existsSync(recoveryFile)) throw failure('找不到该 run_id 的恢复账本');
  const session = fs.existsSync(sessionFile) ? JSON.parse(fs.readFileSync(sessionFile, 'utf8')) : fs.existsSync(recoveryFile)
    ? JSON.parse(fs.readFileSync(recoveryFile, 'utf8')) : JSON.parse(fs.readFileSync(priorFile, 'utf8')).ledger;
  if (session?.run_id !== options.runId || !session.owner_token || !Array.isArray(session.projects)) throw failure('恢复账本身份无效');
  assertInactive(session.main_process);
  const lockFile = path.join(SUITE_ROOT, 'runtime/active.lock');
  if (fs.existsSync(lockFile)) { const lock = JSON.parse(fs.readFileSync(lockFile, 'utf8')); if (lock.main_process) assertInactive(lock.main_process); else if (isLive(lock.pid)) throw failure('suite 锁对应主进程仍活跃', 3); }
  const state = { runtime, artifacts: artifact, temp: runPath('tmp', options.runId), lockFile, session, ownsLock: false };
  session.processes ??= []; session.secret_values ??= []; session.resources_started = !!session.engine; prepareArtifacts(artifact);
  try {
    // 旧报告即使 passed，也重新核验 Engine、标签、进程及残留。
    const result = await withProcessContext({ secrets: session.secret_values, deadline: Date.now() + Math.min(1200000, 180000 + session.projects.length * 45000) }, () => cleanupState(state)); publish(priorFile, result, session);
    const summaryFile = path.join(artifact, 'summary.json');
    const prior = fs.existsSync(summaryFile) ? JSON.parse(fs.readFileSync(summaryFile, 'utf8')) : null;
    writeRunReport(prior ? { ...prior, cleanup_status: result.status, interrupted: prior.final_exit_code === 130 }
      : { run_id: session.run_id, mode: 'Cleanup', started_at: session.created_at ?? timestamp(), finished_at: timestamp(),
        environment_status: 'incomplete', cleanup_status: result.status, counts: {}, original_exit_code: null,
        not_run_reasons: ['原运行未完成最终报告，仅恢复清理资源；环境及产品验收未判定'] }, artifact);
    if (fs.existsSync(lockFile) && JSON.parse(fs.readFileSync(lockFile, 'utf8')).run_id === options.runId && result.status === 'passed') fs.rmSync(lockFile);
    process.stdout.write(`恢复清理：${options.runId}；状态：${result.status}\n`);
    return result.status === 'passed' ? 0 : 4;
  } catch (error) {
    try { publish(priorFile, { run_id: session.run_id, status: 'unknown', errors: [error.message], ledger: publicLedger(session) }, session); }
    catch (reportError) {
      process.stderr.write(sanitizeText(`清理状态报告写入失败，本次清理未通过：${reportError.message}`, session.secret_values) + '\n');
    }
    // 恢复异常也更新摘要，避免旧 cleanup=passed 与本次 unknown 相互矛盾。
    try {
      const summaryFile = path.join(artifact, 'summary.json');
      let prior; try { prior = JSON.parse(fs.readFileSync(summaryFile, 'utf8')); } catch { /* 缺失/损坏时生成未完成恢复摘要。 */ }
      writeRunReport({ ...(prior ?? { run_id: session.run_id, mode: 'Cleanup', started_at: session.created_at ?? timestamp(), environment_status: 'incomplete' }),
        finished_at: timestamp(), cleanup_status: 'unknown', interrupted: prior?.final_exit_code === 130,
        not_run_reasons: [...(prior?.not_run_reasons ?? []), sanitizeText(`恢复清理异常：${error.message}`, session.secret_values)] }, artifact);
    } catch (reportError) {
      process.stderr.write(sanitizeText(`恢复清理摘要更新失败，旧摘要不可作为清理成功证据：${reportError.message}`, session.secret_values) + '\n');
    }
    return 4;
  }
}
export async function resourceHelper(options, adapters = {}) {
  if (!RUN_ID.test(options.runId ?? '') || !['session', 'context', 'model', 'run', 'workspace', 'compatibility', 'performance', 'quality'].includes(options.category)) throw failure('资源helper运行/分类身份无效');
  const allowed = ['inspect', 'restart', 'stop', 'start', 'kill-worker', 'add-worker', 'remove-worker', 'create-probe', 'inspect-probe', 'drop-probe', 'run-test-probe', 'run-pg-cases', 'run-quality-probe', 'scan-secret-images', 'expected-tool-failure', 'audit-public-secrets', 'audit-artifact-secrets', 'observe-run-facts', 'disable-profile', 'restore-profile', 'correlation-logs'];
  if (!allowed.includes(options.action)) throw failure('资源helper动作不在白名单');
  const serviceAction = ['inspect', 'restart', 'stop', 'start'].includes(options.action);
  if (serviceAction && !['api', 'worker', 'provider', 'postgres', 'redis'].includes(options.service)) throw failure('资源helper服务不在白名单');
  // RUN_024 的基础设施故障注入只授予 run 分类，仍须通过下方账本、Engine 和容器归属校验。
  if (serviceAction && ['postgres', 'redis'].includes(options.service) && options.category !== 'run') throw failure('数据库和Redis故障控制仅允许run分类使用');
  if (!serviceAction && options.service) throw failure('此helper动作不接受service参数');
  const runtime = runPath('runtime', options.runId); const sessionFile = path.join(runtime, 'session.json');
  if (!fs.lstatSync(sessionFile).isFile() || fs.lstatSync(sessionFile).isSymbolicLink()) throw failure('资源helper私有账本无效');
  const session = JSON.parse(fs.readFileSync(sessionFile, 'utf8')); const project = session.active_project;
  if (session.run_id !== options.runId || session.active_category !== options.category || !session.projects.includes(project) || project !== `sesrag-ws-${session.run_id.slice(-8)}-${options.category}`) throw failure('资源helper拒绝操作非当前分类project');
  if (!sameProcess(session.main_process, processIdentity(session.main_process?.pid))) throw failure('资源helper所属总运行已停止');
  assertEngine(session.engine, await (adapters.engineIdentity ?? engineIdentity)());
  const command = adapters.runCompose ?? runCompose; const native = adapters.docker ?? docker;
  const operation = { operation_id: crypto.randomUUID(), category: options.category, project, action: options.action, service: options.service ?? null, at: timestamp() };
  const record = (status, detail = null) => {
    const event = JSON.stringify({ ...operation, status, detail: detail ? sanitizeText(detail, session.secret_values) : null }) + '\n';
    fs.appendFileSync(path.join(runtime, 'helper-actions.jsonl'), event, { mode: 0o600 });
    fs.appendFileSync(path.join(runPath('artifacts', session.run_id), 'diagnostics/helper-actions.jsonl'), event, 'utf8');
  };
  const registryPath = path.join(runtime, 'helper-processes.json');
  const registry = fs.existsSync(registryPath) ? JSON.parse(fs.readFileSync(registryPath, 'utf8')) : [];
  const track = (entry, active) => {
    const existing = registry.find((item) => sameProcess(item, entry) || (item.unverified && entry.unverified && item.pid === entry.pid));
    if (existing) Object.assign(existing, entry, { active }); else registry.push({ ...entry, active }); atomicJson(registryPath, registry);
  };
  const verify = async (service) => {
    const ids = (await command(session, project, ['ps', '-a', '-q', service])).split(/\r?\n/).filter(Boolean);
    if (!ids.length) throw failure('资源helper找不到已登记服务容器');
    for (const id of ids) {
      const labels = JSON.parse(await native(['inspect', id]))[0].Config?.Labels;
      if (labels?.['io.sesrag.test.run_id'] !== session.run_id || labels?.['io.sesrag.test.owner'] !== session.owner_token || labels?.['com.docker.compose.project'] !== project) throw failure('资源helper容器归属不符');
    }
    return ids;
  };
  record('intent');
  try {
    const result = await withProcessContext({ secrets: session.secret_values, onProcess: track, deadline: Date.now() + (['run-test-probe', 'run-quality-probe', 'scan-secret-images'].includes(options.action) ? 1500000 : 120000) }, async () => {
      if (options.action === 'kill-worker') {
        if (options.category !== 'run') throw failure('强停Worker只授予run分类');
        await verify('worker'); return command(session, project, ['kill', '-s', 'SIGKILL', 'worker']);
      }
      if (options.action === 'audit-artifact-secrets') {
        if (options.category !== 'quality') throw failure('报告凭据审计只授予quality分类');
        let scanned = 0; let matches = 0;
        const scan = (target) => { const data = fs.readFileSync(target); scanned++; if (session.secret_values.some((value) => value && data.includes(Buffer.from(value)))) matches++; };
        const walk = (directory) => { for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
          const target = path.join(directory, item.name); if (item.isSymbolicLink()) throw failure('报告扫描拒绝符号链接');
          if (item.isDirectory()) walk(target); else scan(target);
        } };
        walk(runPath('artifacts', session.run_id));
        const tracked = await runCommand('git', ['ls-files', '-z'], { cwd: REPO_ROOT });
        if (tracked.code !== 0 || tracked.truncated) throw failure('Git持久面清单不完整');
        for (const relative of tracked.stdout.split('\0').filter(Boolean)) { const target = path.join(REPO_ROOT, relative); if (fs.existsSync(target) && fs.lstatSync(target).isFile()) scan(target); }
        const dist = path.join(REPO_ROOT, 'frontend/dist'); if (!fs.existsSync(dist)) throw failure('缺前端dist，不能宣布扫描完成'); walk(dist);
        return { files_scanned: scanned, files_with_secret: matches, secret_classes: ['model_key', 'control_token', 'postgres_password', 'database_url'] };
      }
      if (serviceAction) {
        const ids = await verify(options.service);
        if (options.action === 'inspect') return Promise.all(ids.map(async (id) => JSON.parse(await native(['inspect', '--format', '{{json .State}}', id]))));
        const output = await command(session, project, [options.action, ...(options.action === 'restart' || options.action === 'stop' ? ['--timeout', '30'] : []), options.service]);
        // Docker对published=0的服务重启时可能重新分配宿主端口，调用方须更新观察地址。
        if (['restart', 'start'].includes(options.action) && options.service === 'api') return { output, api_base_url: `http://127.0.0.1:${await publishedPort(session, project, 'api', 8000)}` };
        return output;
      }
      if (options.action === 'run-test-probe') {
        if (options.category === 'workspace' || options.category === 'performance' || options.category === 'quality') throw failure('该分类使用专用测试执行器');
        const pg = (await verify('postgres'))[0];
        const server = await native(['exec', pg, 'psql', '-U', 'sesrag', '-d', 'sesrag_workspace', '-Atc', 'SELECT system_identifier FROM pg_control_system()']);
        return runTools(session, project, ['/suite/specific_test_script/probes/backend-regression-probe.py', '--category', options.category, '--expected-server-id', server, '--expected-namespace', project], 1100000);
      }
      if (options.action === 'observe-run-facts') {
        if (options.category !== 'run') throw failure('Run事实只读探针只授予run分类');
        const pg = (await verify('postgres'))[0];
        const server = await native(['exec', pg, 'psql', '-U', 'sesrag', '-d', 'sesrag_workspace', '-Atc', 'SELECT system_identifier FROM pg_control_system()']);
        return runTools(session, project, ['/suite/specific_test_script/probes/run-facts.py', '--expected-server-id', server, '--expected-namespace', project]);
      }
      if (options.action === 'correlation-logs') {
        if (options.category !== 'run') throw failure('结构化关联观察只授予run分类');
        await verify('worker'); const logs = await command(session, project, ['logs', '--no-color', 'worker']); const records = [];
        for (const line of logs.split(/\r?\n/)) { const start = line.indexOf('{'); if (start < 0) continue;
          let record; try { record = JSON.parse(line.slice(start)); } catch { continue; }
          if (record.run_id && record.task_id) records.push(Object.fromEntries(['action', 'run_id', 'task_id', 'worker_id', 'generation', 'attempt', 'error_code'].map((field) => [field, record[field] ?? null])));
        }
        return { records };
      }
      if (['disable-profile', 'restore-profile'].includes(options.action)) {
        if (options.category !== 'workspace') throw failure('可用性fixture只授予workspace分类');
        const pg = (await verify('postgres'))[0];
        const status = options.action === 'disable-profile' ? 'disabled' : 'enabled';
        return native(['exec', pg, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'sesrag', '-d', 'sesrag_workspace', '-Atc', `UPDATE model_profiles SET status='${status}' WHERE profile_id='ws-http-b' AND version=1 AND NOT is_default RETURNING profile_id,status`]);
      }
      if (options.action === 'run-pg-cases') {
        if (!['session', 'run'].includes(options.category)) throw failure('PG竞争探针只授予session/run分类');
        const pg = (await verify('postgres'))[0];
        const server = await native(['exec', pg, 'psql', '-U', 'sesrag', '-d', 'sesrag_workspace', '-Atc', 'SELECT system_identifier FROM pg_control_system()']);
        return runTools(session, project, ['/suite/specific_test_script/probes/postgres-cases.py', '--category', options.category, '--expected-server-id', server, '--expected-namespace', project], 120000);
      }
      if (options.action === 'audit-public-secrets') {
        if (!['model', 'run', 'quality'].includes(options.category)) throw failure('凭据审计仅授予model/run/quality分类');
        const logs = await command(session, project, ['logs', '--no-color'], { timeoutMs: 60000 });
        const hits = session.secret_values.filter((value) => value && logs.includes(value)).length;
        await runTools(session, project, ['-c', `import os,runpy;os.environ['WORKSPACE_PROBE_CATEGORY']=${JSON.stringify(options.category)};runpy.run_path('/suite/specific_test_script/probes/secret-facts-probe.py',run_name='__main__')`]);
        return { log_secret_matches: hits, logs_bytes: Buffer.byteLength(logs), fact_scan_file: 'secret-facts.json' };
      }
      if (['run-quality-probe', 'scan-secret-images', 'expected-tool-failure'].includes(options.action)) {
        if (options.category !== 'quality') throw failure('质量动作仅授予quality分类');
        if (options.action === 'run-quality-probe') return runTools(session, project, ['/suite/specific_test_script/probes/quality-probe.py'], 1400000);
        if (options.action === 'scan-secret-images') {
          const archive = path.join(runPath('tmp', session.run_id), 'quality/secret-images.tar');
          await native(['image', 'save', '--output', archive, ...session.images.map((item) => item.tag)], { timeoutMs: 300000 });
          return runTools(session, project, ['/suite/specific_test_script/probes/scan-images.py'], 300000);
        }
        try { await runTools(session, project, ['-c', 'raise SystemExit(19)'], 30000); }
        catch (error) {
          if (isExpectedToolExit(error)) return { expected_exit_observed: true, exit_code: 19 };
          throw error;
        }
        throw failure('受控失败没有产生非零退出');
      }
      if (options.action === 'add-worker' || options.action === 'remove-worker') {
        await verify('worker');
        return command(session, project, ['up', '-d', '--no-build', '--no-deps', '--scale', `worker=${options.action === 'add-worker' ? 2 : 1}`, 'worker']);
      }
      const pg = (await command(session, project, ['ps', '-a', '-q', 'postgres'])).trim();
      const labels = JSON.parse(await native(['inspect', pg]))[0].Config?.Labels;
      if (labels?.['io.sesrag.test.run_id'] !== session.run_id || labels?.['io.sesrag.test.owner'] !== session.owner_token || labels?.['com.docker.compose.project'] !== project) throw failure('专库helper PostgreSQL归属不符');
      const server = await native(['exec', pg, 'psql', '-U', 'sesrag', '-d', 'sesrag_workspace', '-Atc', 'SELECT system_identifier FROM pg_control_system()']);
      if (!/^\d+$/.test(server)) throw failure('专库helper服务端身份无效');
      return runTools(session, project, ['/suite/tooling/db-admin.py', options.action.split('-')[0], '--database', `sesrag_session_probe_${session.run_id.slice(-8)}`, '--expected-server-id', server, '--expected-namespace', project]);
    });
    record('completed'); return { schema_version: 1, status: 'passed', operation_id: operation.operation_id, result: typeof result === 'string' ? sanitizeText(result, session.secret_values) : result };
  } catch (error) { record('failed', error.message); throw failure(sanitizeText(error.message, session.secret_values), error.exitCode ?? 2); }
}
function helperOptions(args) {
  const out = {};
  for (let index = 0; index < args.length; index += 2) {
    const key = { '--run-id': 'runId', '--category': 'category', '--action': 'action', '--service': 'service' }[args[index]];
    if (!key || !args[index + 1] || out[key]) throw failure('资源helper参数无效或重复'); out[key] = args[index + 1];
  }
  return out;
}
async function entry() {
  try {
    const args = process.argv.slice(2);
    if (args[0] === '--resource-helper') { const result = await resourceHelper(helperOptions(args.slice(1))); process.stdout.write(JSON.stringify(result) + '\n'); return 0; }
    const options = parseOptions(args); return options.mode === 'Cleanup' ? await cleanupMode(options) : await mainRun(options);
  }
  catch (error) { process.stderr.write(`运行器错误：${sanitizeText(error.message)}\n`); return error.exitCode ?? 2; }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  entry().then((code) => { process.exitCode = code; }).catch((error) => { process.stderr.write(sanitizeText(error.message) + '\n'); process.exitCode = 2; });
}
