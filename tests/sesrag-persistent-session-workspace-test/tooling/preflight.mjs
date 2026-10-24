import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { readCaseCatalog, assertCompleteRegistration } from './case-catalog.mjs';

export const SUITE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const REPO_ROOT = path.resolve(SUITE_ROOT, '..', '..');
const CATEGORY_IDS = ['session', 'context', 'model', 'run', 'workspace', 'compatibility', 'performance', 'quality'];
const REQUIREMENT_IDS = [
  'FR-TH-01', 'FR-TH-02', 'FR-MEM-01', 'FR-BR-01', 'FR-BR-02', 'FR-MOD-01', 'FR-MOD-02',
  'FR-STR-01', 'FR-STR-02', 'FR-REC-01', 'FR-REC-02', 'FR-RUN-01', 'FR-OBS-01', 'FR-CTX-01',
  'FR-CTX-02', 'FR-MD-01', 'FR-RAG-01', 'FR-ERR-01', 'NFR-SEC-01', 'NFR-SEC-02', 'NFR-ISO-01',
  'NFR-REL-01', 'NFR-REL-02', 'NFR-PERF-01', 'NFR-CAP-01', 'NFR-OBS-01', 'NFR-TEST-01',
  'NFR-MIG-01', 'NFR-DEP-01',
];
const SOURCE_ROOTS = ['backend', 'frontend/src', 'frontend/scripts', 'frontend/tests', 'contracts', 'migrations', 'docker', 'tests/unit', 'tests/api', 'tests/integration', 'tests/sesrag-persistent-session-workspace-test'];
const SOURCE_FILES = ['pyproject.toml', 'alembic.ini', '.dockerignore', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.ts', 'frontend/vitest.config.ts', 'frontend/eslint.config.mjs', 'frontend/tsconfig.json', 'frontend/index.html', 'tests/sesrag-persistent-session-workspace-test/test-cases.md'];
const EXCLUDED_DIRS = new Set(['runtime', 'artifacts', 'tmp', 'node_modules', '.cache', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist']);
const SECRET_FILE = /(?:^|\/)(?:\.env(?:\..*)?|.*\.local)$/i;
const SUITE_PREFIX = 'tests/sesrag-persistent-session-workspace-test/';

export function validateManifest(manifest, suiteRoot = SUITE_ROOT) {
  if (!manifest || manifest.schema_version !== 1 || !Array.isArray(manifest.categories)) {
    throw new TypeError('manifest 必须是 schema_version=1 且含 categories 数组');
  }
  const ids = manifest.categories.map((item) => item?.category);
  if (JSON.stringify(ids) !== JSON.stringify(CATEGORY_IDS)) {
    throw new TypeError('manifest 分类必须按 TEST-002 登记的 8 类及顺序排列');
  }
  const seenCases = new Set();
  const requirements = new Set();
  const catalog = readCaseCatalog(suiteRoot);
  for (const entry of manifest.categories) {
    if (typeof entry.required !== 'boolean' || !['planned', 'ready'].includes(entry.status)) {
      throw new TypeError(`分类 ${entry.category} 的 required/status 无效`);
    }
    if (!entry.required) throw new TypeError(`分类 ${entry.category} 是必需分类，不得降为可选`);
    if (!Number.isInteger(entry.timeout_seconds) || entry.timeout_seconds < 1 || entry.timeout_seconds > 1800) {
      throw new TypeError(`分类 ${entry.category} 的超时必须为 1～1800 秒`);
    }
    if (!Array.isArray(entry.case_ids) || !Array.isArray(entry.requirements)) {
      throw new TypeError(`分类 ${entry.category} 必须提供 case_ids 和 requirements 数组`);
    }
    if (entry.status === 'planned' && (entry.script !== null || entry.case_ids.length !== 0)) {
      throw new TypeError(`planned 分类 ${entry.category} 不能绑定脚本或空壳 case`);
    }
    if (entry.status === 'ready') {
      if (typeof entry.script !== 'string' || !entry.case_ids.length) {
        throw new TypeError(`ready 分类 ${entry.category} 必须登记脚本和 case ID`);
      }
      const scriptPath = path.resolve(suiteRoot, entry.script);
      const scriptsRoot = path.resolve(suiteRoot, 'specific_test_script') + path.sep;
      if (!scriptPath.startsWith(scriptsRoot) || !fs.existsSync(scriptPath)) {
        throw new TypeError(`分类 ${entry.category} 脚本路径不存在或越界`);
      }
      if (!fs.lstatSync(scriptPath).isFile() || fs.lstatSync(scriptPath).isSymbolicLink()
          || !fs.realpathSync(scriptPath).startsWith(fs.realpathSync(path.join(suiteRoot, 'specific_test_script')) + path.sep)) {
        throw new TypeError(`分类 ${entry.category} 脚本包含链接或真实路径越界`);
      }
      if (!/\.(mjs|ps1)$/.test(scriptPath)) throw new TypeError('分类脚本仅允许 .mjs 或 .ps1');
      assertCompleteRegistration(entry, catalog);
    }
    for (const caseId of entry.case_ids) {
      if (typeof caseId !== 'string' || !caseId || seenCases.has(caseId)) {
        throw new TypeError(`case ID 无效或重复：${caseId}`);
      }
      seenCases.add(caseId);
    }
    for (const requirement of entry.requirements) {
      if (!REQUIREMENT_IDS.includes(requirement)) throw new TypeError(`未知需求 ID：${requirement}`);
      requirements.add(requirement);
    }
  }
  const missing = REQUIREMENT_IDS.filter((id) => !requirements.has(id));
  if (missing.length) throw new TypeError(`manifest 未映射全部 FR/NFR：${missing.join(', ')}`);
  return { category_count: ids.length, required_count: manifest.categories.filter((item) => item.required).length, case_count: seenCases.size, designed_case_count: catalog.case_count, mapped_requirement_count: requirements.size };
}

function hashFile(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function collectSourceFiles() {
  const paths = [...SOURCE_FILES];
  for (const root of SOURCE_ROOTS) {
    const absolute = path.join(REPO_ROOT, root);
    if (!fs.existsSync(absolute)) continue;
    const walk = (directory) => {
      for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
        if (item.isSymbolicLink()) throw new Error(`源码树内不允许符号链接：${item.name}`);
        const full = path.join(directory, item.name);
        const relative = path.relative(REPO_ROOT, full).split(path.sep).join('/');
        if (item.isDirectory()) {
          if (!EXCLUDED_DIRS.has(item.name)) walk(full);
        } else if (!SECRET_FILE.test(relative)) {
          // 交付记录/说明不是可执行输入；fixture 的 Markdown 原文仍须参加指纹。
          if (relative.startsWith(SUITE_PREFIX) && relative.endsWith('.md')
              && !relative.startsWith(`${SUITE_PREFIX}fixtures/`)) continue;
          paths.push(relative);
        }
      }
    };
    walk(absolute);
  }
  return [...new Set(paths)].filter((relative) => fs.existsSync(path.join(REPO_ROOT, relative))).sort();
}

export function buildSourceManifest() {
  const files = collectSourceFiles().map((relative) => ({ path: relative, sha256: hashFile(path.join(REPO_ROOT, relative)) }));
  const digest = crypto.createHash('sha256').update(files.map((item) => `${item.path}\0${item.sha256}`).join('\n')).digest('hex');
  let head = null;
  let dirtyPaths = [];
  try {
    head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: REPO_ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    const status = execFileSync('git', ['status', '--short', '--untracked-files=all', '--', ...SOURCE_ROOTS, ...SOURCE_FILES], { cwd: REPO_ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    dirtyPaths = status.split(/\r?\n/).filter(Boolean).map((line) => line.slice(3)).filter(Boolean);
  } catch {
    dirtyPaths = ['Git 状态不可用'];
  }
  return { head, source_digest: digest, file_count: files.length, dirty_paths: dirtyPaths, files };
}

function validateJsonSchemas() {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const schemaDir = path.join(SUITE_ROOT, 'schemas');
  const results = [];
  for (const name of ['run-context.schema.json', 'category-result.schema.json', 'run-summary.schema.json']) {
    const schema = JSON.parse(fs.readFileSync(path.join(schemaDir, name), 'utf8'));
    ajv.compile(schema);
    results.push(name);
  }
  return results;
}

export async function runPreflight({ browserSelfTest = false } = {}) {
  const nodeMajor = Number(process.versions.node.split('.')[0]);
  if (nodeMajor !== 24) throw new Error(`需要 Node.js 24 LTS，当前为 ${process.versions.node}`);
  const manifest = JSON.parse(fs.readFileSync(path.join(SUITE_ROOT, 'specific_test_script/manifest.json'), 'utf8'));
  const manifestSummary = validateManifest(manifest);
  const schemas = validateJsonSchemas();
  const sourceManifest = buildSourceManifest();
  let browser = { status: 'not_checked' };
  if (browserSelfTest) {
    // 在动态加载 Playwright 前固定缓存，防止解析到用户全局浏览器。
    process.env.PLAYWRIGHT_BROWSERS_PATH = path.join(SUITE_ROOT, '.cache/ms-playwright');
    const { chromium } = await import('playwright');
    const instance = await chromium.launch({ headless: true });
    try {
      const page = await instance.newPage();
      await page.goto('about:blank');
      browser = { status: 'passed', browser_version: instance.version(), page_url: page.url() };
    } finally { await instance.close(); }
  }
  return {
    schema_version: 1,
    status: 'passed',
    node_version: process.versions.node,
    manifest: manifestSummary,
    categories: manifest.categories.map(({ category, required, status, case_ids }) => ({ category, required, status, case_count: case_ids.length })),
    schemas,
    browser,
    source_manifest: sourceManifest,
  };
}

async function main() {
  const result = await runPreflight({ browserSelfTest: process.argv.includes('--browser-self-test') });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`预检失败：${error.message}\n`);
    process.exitCode = 2;
  });
}
