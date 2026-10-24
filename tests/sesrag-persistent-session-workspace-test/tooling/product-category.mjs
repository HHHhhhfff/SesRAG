import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { runCommand } from './process-registry.mjs';
import { assertSafeArtifactPath, sanitizeText } from './report.mjs';

export const suiteRoot = fileURLToPath(new URL('../', import.meta.url));
export const repoRoot = path.resolve(suiteRoot, '../..');
const prefixes = { session: 'SES', context: 'CTX', model: 'MOD', run: 'RUN', compatibility: 'COMP', workspace: 'UI', performance: 'PERF', quality: 'QLT' };

// 正式用例的预期只作报告输入；实际判定必须由分类函数的断言产生。
export function parseCases(category) {
  const text = fs.readFileSync(path.join(suiteRoot, 'test-cases.md'), 'utf8');
  const result = []; let item;
  for (const line of text.split(/\r?\n/)) {
    const heading = /^#### ([A-Z]+_\d{3}) (.+)$/.exec(line);
    if (heading) {
      if (item) result.push(item);
      item = heading[1].startsWith(`${prefixes[category]}_`) ? { case_id: heading[1], title: heading[2], points: [], expected: '', type: '功能', priority: 'P1' } : null;
      continue;
    }
    if (!item) continue;
    if (line.startsWith('- 对应测试点：')) item.points = [...new Set([...line.matchAll(/TP-[A-Z]+-\d+/g)].map((match) => match[0]))];
    if (line.startsWith('- 预期结果：')) item.expected = line.slice('- 预期结果：'.length).trim();
    if (line.startsWith('- 用例类型：')) item.type = line.slice('- 用例类型：'.length).trim();
  }
  if (item) result.push(item);
  const requirementByPoint = new Map();
  for (const line of fs.readFileSync(path.join(suiteRoot, '测试点设计与需求覆盖矩阵.md'), 'utf8').split(/\r?\n/)) {
    const cells = line.split('|').map((cell) => cell.trim());
    if (!/^(FR|NFR)-[A-Z]+-\d+$/.test(cells[1] ?? '')) continue;
    const expanded = cells[2].replace(/(TP-[A-Z]+-)(\d+)～(?:TP-[A-Z]+-)?(\d+)/g, (_all, prefix, low, high) =>
      Array.from({ length: Number(high) - Number(low) + 1 }, (_, index) => `${prefix}${String(Number(low) + index).padStart(2, '0')}`).join('、'));
    for (const [point] of expanded.matchAll(/TP-[A-Z]+-\d+/g)) requirementByPoint.set(point, [...(requirementByPoint.get(point) ?? []), cells[1]]);
  }
  for (const testCase of result) {
    testCase.requirements = [...new Set(testCase.points.flatMap((point) => requirementByPoint.get(point) ?? []))];
    if (!testCase.points.length || !testCase.expected || !testCase.requirements.length) throw new Error(`用例追溯字段缺失：${testCase.case_id}`);
  }
  return result;
}

export function atomicJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.${process.pid}.${crypto.randomUUID()}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(data, null, 2)}\n`, { flag: 'wx' });
  fs.renameSync(temporary, file);
}

// 全部动态凭据仅由父进程私有环境授予，不进入context、argv、浏览器或报告。
export function evidenceSecrets(environment = process.env) {
  const values = JSON.parse(environment.WS_EVIDENCE_SECRETS ?? '[]');
  if (!Array.isArray(values) || values.some((value) => typeof value !== 'string' || !value)) throw new Error('私有证据脱敏集合无效');
  return [...new Set([...values, environment.PROVIDER_CONTROL_TOKEN, environment.MODEL_API_KEY].filter(Boolean))];
}
export function redactEvidence(value, secrets) {
  return typeof value === 'string' ? sanitizeText(value, secrets) : Array.isArray(value) ? value.map((item) => redactEvidence(item, secrets))
    : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([name, item]) => [sanitizeText(name, secrets), redactEvidence(item, secrets)])) : value;
}

export async function helper(context, action, service) {
  const run = await runCommand(process.execPath, [path.join(suiteRoot, context.resource_helper), '--resource-helper', '--run-id', context.run_id,
    '--category', context.category, '--action', action, ...(service ? ['--service', service] : [])], { cwd: suiteRoot, timeoutMs: 1200000, maxBytes: 8 * 1024 * 1024 });
  if (run.code !== 0 || run.timedOut || run.truncated) throw new Error(`受限helper失败：${action}；${sanitizeText(run.stderr || run.stdout)}`);
  return JSON.parse(run.stdout.trim().split(/\r?\n/).at(-1));
}

export function openCategory(category, contextFile) {
  const context = JSON.parse(fs.readFileSync(contextFile, 'utf8'));
  if (context.category !== category) throw new Error('分类与上下文身份不符');
  const cases = parseCases(category);
  if (JSON.stringify(cases.map((item) => item.case_id).sort()) !== JSON.stringify([...context.expected_case_ids].sort())) throw new Error('分类登记与正式用例清单不一致');
  const root = path.resolve(suiteRoot, context.artifact_dir); fs.mkdirSync(root, { recursive: true });
  const tmp = path.resolve(suiteRoot, context.tmp_dir); fs.mkdirSync(tmp, { recursive: true });
  const started = new Date().toISOString(); const outputs = [];
  const secrets = evidenceSecrets();
  return {
    context, cases, root, tmp,
    evidence(name, value) {
      const relative = `categories/${category}/${name}`; assertSafeArtifactPath(relative);
      const cleaned = redactEvidence(value, secrets);
      const text = typeof cleaned === 'string' ? cleaned : JSON.stringify(cleaned, null, 2);
      const target = path.join(suiteRoot, 'artifacts', context.run_id, relative);
      fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, text + '\n');
      return relative;
    },
    async test(id, action) {
      const testCase = cases.find((entry) => entry.case_id === id);
      if (!testCase || outputs.some((entry) => entry.case_id === id)) throw new Error(`未知或重复用例：${id}`);
      const before = performance.now(); let observation;
      console.log(`【${id}】开始：${testCase.title}`);
      try { observation = await action(testCase); }
      catch (error) { observation = { status: 'failed', actual: sanitizeText(error.message, secrets), test_error_location: sanitizeText(error.stack ?? '', secrets), reason_code: 'ASSERTION_FAILED', reason: '实际操作或断言未满足预期，见逐例证据。' }; }
      observation = redactEvidence(observation, secrets);
      const status = observation.status ?? 'passed';
      const evidence = this.evidence(`${id}.json`, { case_id: id, expected: testCase.expected, observation });
      const entry = { case_id: id, test_point_ids: testCase.points, requirement_ids: testCase.requirements, title: testCase.title, type: testCase.type,
        status, expected: testCase.expected, actual: observation.actual || JSON.stringify(observation), reason_code: status === 'passed' ? null : observation.reason_code ?? 'TEST_PRECONDITION_MISSING',
        reason: status === 'passed' ? null : observation.reason ?? observation.actual, evidence_paths: [evidence, ...(observation.evidence_paths ?? [])], duration_ms: performance.now() - before };
      outputs.push(entry);
      console.log(`【${id}】${{ passed: '通过', failed: '失败', blocked: '受限', not_run: '未执行' }[status]}：${entry.actual}`);
      return entry;
    },
    finish() {
      if (outputs.length !== cases.length) throw new Error(`分类逐例结果不完整：${outputs.length}/${cases.length}`);
      const status = outputs.some((item) => item.status === 'failed') ? 'failed' : outputs.some((item) => item.status !== 'passed') ? 'blocked' : 'passed';
      atomicJson(path.join(root, 'result.json'), { schema_version: 1, run_id: context.run_id, environment_id: context.environment_id, category,
        started_at: started, finished_at: new Date().toISOString(), status, cases: outputs, evidence: [...new Set(outputs.flatMap((item) => item.evidence_paths))] });
      return { passed: 0, failed: 1, blocked: 3 }[status];
    },
  };
}

export async function runBackendRegressionCategory(category, contextFile, runtimeCases = {}) {
  const suite = openCategory(category, contextFile);
  await helper(suite.context, 'run-test-probe');
  const regression = JSON.parse(fs.readFileSync(path.join(suite.tmp, 'backend-regression.json'), 'utf8'));
  const evidence = ['backend-regression.json', 'pytest-regression.xml', 'pytest-regression.log'].map((name) => suite.evidence(name, fs.readFileSync(path.join(suite.tmp, name), 'utf8')));
  let pg;
  if (['session', 'run'].includes(category)) {
    await helper(suite.context, 'run-pg-cases');
    pg = JSON.parse(fs.readFileSync(path.join(suite.tmp, 'postgres-cases.json'), 'utf8'));
    evidence.push(suite.evidence('postgres-cases.json', pg));
  }
  for (const testCase of suite.cases) await suite.test(testCase.case_id, async () => {
    const found = regression.case_results.find((entry) => entry.case_id === testCase.case_id);
    if (!found) throw new Error('探针缺少逐例观察');
    const special = found.test_nodes.filter((node) => node.startsWith('@pg::')).map((node) => pg?.results.find((entry) => entry.name === node.slice(5)));
    if (special.some((entry) => !entry || entry.status !== 'passed')) throw new Error(`真实PG断言失败：${JSON.stringify(special)}`);
    const missing = found.missing_targets.filter((node) => !node.startsWith('@pg::'));
    if (special.length && !missing.length && found.observations.every((item) => item.status === 'passed')) found.status = 'passed';
    if (runtimeCases[testCase.case_id]) {
      const observed = await runtimeCases[testCase.case_id](suite);
      if (found.status === 'failed') throw new Error('关联回归断言失败；运行时子场景的成功不能覆盖失败');
      if (found.test_nodes.length && found.status !== 'passed') return { ...found, evidence_paths: evidence, actual: `关联节点未全部执行或有跳过：${found.missing_targets.join('；')}` };
      return { ...observed, evidence_paths: evidence, pg_observations: special };
    }
    return { ...found, evidence_paths: evidence, actual: `${found.status === 'failed' ? '指定断言失败：' : '已执行：'}${found.test_count}个pytest节点${special.length ? `及${special.length}组真实PG场景` : ''}；${found.status === 'failed' ? found.observations.filter((item) => item.status !== 'passed').map((item) => item.node).join('；') : found.test_nodes.join('；')}`, pg_observations: special };
  });
  return suite.finish();
}
