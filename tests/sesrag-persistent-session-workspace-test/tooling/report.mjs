import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const schemaPath = new URL('../schemas/run-summary.schema.json', import.meta.url);
const knownHostRoots = [fileURLToPath(new URL('../../../', import.meta.url)), fileURLToPath(new URL('../', import.meta.url))].map((root) => path.resolve(root));

export function sanitizeText(value, secrets = [], hostRoots = knownHostRoots) {
  let text = String(value ?? '');
  for (const root of [...hostRoots].filter(Boolean).sort((a, b) => b.length - a.length)) {
    for (const variant of new Set([root, root.replace(/\\/g, '/'), encodeURI(root.replace(/\\/g, '/'))])) text = text.split(variant).join('[宿主路径已脱敏]');
  }
  for (const secret of [...secrets].filter(Boolean).sort((a, b) => b.length - a.length)) {
    text = text.split(String(secret)).join('[已脱敏]');
  }
  return text
    .replace(/\bBearer\s+[^\s"'<>]+/gi, 'Bearer [已脱敏]')
    .replace(/\b(?:postgres(?:ql)?(?:\+psycopg)?:\/\/)[^\s"'<>]+/gi, '[已脱敏数据库 DSN]')
    .replace(/\b((?:[a-z]+_)*password|(?:[a-z]+_)*api[_-]?key|provider[_-]?control[_-]?token)\s*[:=]\s*[^\s,;"']+/gi, '$1=[已脱敏]')
    .replace(/\b[A-Za-z]:\\(?:[^\\\r\n"'<>]+\\)*[^\\\r\n"'<>]*/g, '[宿主路径已脱敏]')
    .replace(/\\\\[^\\\s]+\\[^\s"'<>]+/g, '[宿主 UNC 路径已脱敏]');
}

export function assertSafeArtifactPath(relativePath) {
  if (typeof relativePath !== 'string' || !relativePath || /[\\:\x00-\x1f]/.test(relativePath)) {
    throw new TypeError('证据路径必须是非空 POSIX 相对路径');
  }
  if (relativePath.startsWith('/') || /^[A-Za-z]:/.test(relativePath)) {
    throw new TypeError('证据路径不能是绝对路径');
  }
  const parts = relativePath.split('/');
  if (parts.some((part) => !part || part === '.' || part === '..')) {
    throw new TypeError('证据路径包含空段或路径逃逸');
  }
  if (parts[0] !== 'categories' && parts[0] !== 'diagnostics' && parts[0] !== 'browser' && parts[0] !== 'services') {
    throw new TypeError('证据路径必须位于本轮 artifact 证据目录');
  }
  return true;
}

function emptyCounts(source = {}) {
  return Object.fromEntries(
    ['passed', 'failed', 'blocked', 'not_run', 'harness_error'].map((key) => [key, Number(source[key] ?? 0)]),
  );
}

export function buildRunSummary(input) {
  const counts = emptyCounts(input.counts);
  const mode = input.mode;
  let environmentStatus = input.environment_status ?? 'not_run';
  let productAcceptance = input.product_acceptance ?? 'not_run';
  const cleanupStatus = input.cleanup_status ?? 'not_required';
  const unready = input.unready_categories ?? [];
  let exitCode = Number.isInteger(input.original_exit_code) ? input.original_exit_code : 0;

  if (mode === 'Environment') {
    productAcceptance = 'not_run';
    if (environmentStatus !== 'passed' && !['failed', 'incomplete'].includes(environmentStatus)) {
      environmentStatus = 'blocked';
    }
    exitCode = environmentStatus === 'passed' ? 0 : (input.original_exit_code === 2 ? 2 : 3);
  } else if (mode === 'All' && unready.length > 0) {
    environmentStatus = 'not_run';
    productAcceptance = 'incomplete';
    exitCode = 3;
  } else if (mode === 'Selected' || mode === 'All') {
    if (counts.harness_error > 0) {
      productAcceptance = 'incomplete';
      exitCode = 2;
    } else if (counts.failed > 0) {
      productAcceptance = 'failed';
      exitCode = 1;
    } else if (counts.blocked > 0 || counts.not_run > 0) {
      productAcceptance = 'incomplete';
      exitCode = 3;
    } else if (counts.passed > 0 && environmentStatus === 'passed') {
      productAcceptance = mode === 'All' ? 'passed' : 'partial';
      exitCode = 0;
    } else {
      productAcceptance = 'incomplete';
      exitCode = 3;
    }
  } else if (mode === 'Cleanup') {
    productAcceptance = 'not_run';
    exitCode = cleanupStatus === 'passed' ? 0 : 4;
  } else {
    throw new TypeError(`未知运行模式：${mode}`);
  }

  if (input.original_exit_code === 2 && [0, 1, 3].includes(exitCode)) exitCode = 2;
  if (mode === 'All' && productAcceptance === 'passed' && input.quality_prerequisites !== 'ready') { productAcceptance = 'incomplete'; if (exitCode === 0) exitCode = 3; }
  if (cleanupStatus === 'failed' || cleanupStatus === 'unknown' || input.original_exit_code === 4) exitCode = 4;
  else if (input.interrupted === true && cleanupStatus === 'passed') exitCode = 130;
  else if (exitCode === 0 && input.original_exit_code && input.original_exit_code !== 0) {
    exitCode = input.original_exit_code;
  }

  return {
    schema_version: 1,
    run_id: input.run_id,
    mode,
    started_at: input.started_at,
    finished_at: input.finished_at,
    environment_status: environmentStatus,
    product_acceptance: productAcceptance,
    cleanup_status: cleanupStatus,
    source_unchanged: input.source_unchanged ?? null,
    frozen_build: input.frozen_build ?? null,
    quality_prerequisites: input.quality_prerequisites ?? 'pending',
    selected_categories: input.selected_categories ?? [],
    required_categories: input.required_categories ?? [],
    counts,
    original_exit_code: input.original_exit_code ?? null,
    final_exit_code: exitCode,
    not_run_reasons: input.not_run_reasons ?? [],
    warnings: input.warnings ?? [],
  };
}

function validateSummary(value) {
  const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const validate = ajv.compile(schema);
  if (!validate(value)) throw new Error(`运行报告不符合 Schema：${JSON.stringify(validate.errors)}`);
}

function atomicJson(filePath, value) {
  const tempPath = `${filePath}.${process.pid}.tmp`;
  fs.writeFileSync(tempPath, `${JSON.stringify(value, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(tempPath, filePath);
}

function evidenceIndex(artifactRoot) {
  const entries = [];
  const walk = (directory) => {
    for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
      const full = path.join(directory, item.name);
      if (item.isSymbolicLink()) throw new Error(`artifact 中不允许符号链接：${item.name}`);
      if (item.isDirectory()) walk(full);
      else if (!['evidence-index.json', 'summary.json', 'summary.md'].includes(item.name)) {
        const stat = fs.statSync(full);
        const bytes = fs.readFileSync(full);
        entries.push({
          path: path.relative(artifactRoot, full).split(path.sep).join('/'),
          bytes: stat.size,
          sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
        });
      }
    }
  };
  walk(artifactRoot);
  return { schema_version: 1, entries };
}

function summaryMarkdown(summary) {
  const labels = {
    passed: '通过', failed: '失败', blocked: '受限', incomplete: '未完成', not_run: '未运行',
    unknown: '未知', not_required: '无需清理', partial: '部分验收',
  };
  return [
    '# 本机隔离测试运行摘要',
    '',
    `- 运行 ID：\`${summary.run_id}\``,
    `- 模式：${summary.mode}`,
    `- 环境：${labels[summary.environment_status] ?? summary.environment_status}`,
    `- 产品验收：${labels[summary.product_acceptance] ?? summary.product_acceptance}`,
    `- 清理：${labels[summary.cleanup_status] ?? summary.cleanup_status}`,
    `- 源码未变化：${summary.source_unchanged === null ? '未判定' : summary.source_unchanged ? '是' : '否'}`,
    `- 最终退出码：${summary.final_exit_code}`,
    `- 用例计数：通过 ${summary.counts.passed}，失败 ${summary.counts.failed}，受限 ${summary.counts.blocked}，未运行 ${summary.counts.not_run}，运行器错误 ${summary.counts.harness_error}`,
    '',
    '## 未运行原因',
    '',
    ...(summary.not_run_reasons.length ? summary.not_run_reasons.map((item) => `- ${item}`) : ['- 无']),
    '',
    'Environment 模式不运行产品用例；环境通过不代表 PRD 功能验收通过。',
    '',
  ].join('\n');
}

export function writeRunReport(input, artifactRoot) {
  fs.mkdirSync(artifactRoot, { recursive: true });
  const summary = buildRunSummary(input);
  validateSummary(summary);
  const index = evidenceIndex(artifactRoot);
  atomicJson(path.join(artifactRoot, 'summary.json'), summary);
  fs.writeFileSync(path.join(artifactRoot, 'summary.md'), summaryMarkdown(summary), 'utf8');
  atomicJson(path.join(artifactRoot, 'evidence-index.json'), index);
  return summary;
}

async function main() {
  const args = process.argv.slice(2);
  const inputIndex = args.indexOf('--input');
  const artifactIndex = args.indexOf('--artifact-dir');
  if (inputIndex < 0 || artifactIndex < 0 || !args[inputIndex + 1] || !args[artifactIndex + 1]) {
    throw new Error('用法：node report.mjs --input <summary-input.json> --artifact-dir <artifact-dir>');
  }
  const input = JSON.parse(fs.readFileSync(args[inputIndex + 1], 'utf8'));
  const artifactRoot = path.resolve(args[artifactIndex + 1]);
  fs.mkdirSync(artifactRoot, { recursive: true });
  const summary = writeRunReport(input, artifactRoot);
  process.stdout.write(`${summaryMarkdown(summary)}\n`);
  process.exitCode = summary.final_exit_code;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`${sanitizeText(error.stack ?? error.message)}\n`);
    process.exitCode = 2;
  });
}
