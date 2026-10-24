import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { buildSourceManifest, REPO_ROOT, SUITE_ROOT } from './preflight.mjs';

// 只解析 Compose 配置，不连接 Engine、不启动容器，也不读取开发 .env。
function config() {
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/^(WS_TEST_|COMPOSE_)/i.test(key)));
  Object.assign(env, {
    WS_TEST_REPO_ROOT: REPO_ROOT.replaceAll('\\', '/'), WS_TEST_TMP_DIR: SUITE_ROOT.replaceAll('\\', '/'),
    WS_TEST_RUN_ID: 'ws-20261021t000000z-abcdef12', WS_TEST_OWNER_TOKEN: 'synthetic-owner',
    WS_TEST_PROJECT: 'sesrag-ws-abcdef12-env', WS_TEST_CATEGORY: 'session',
    WS_TEST_SOURCE_DIGEST: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    WS_TEST_APP_IMAGE: 'sesrag-ws-app:config-only', WS_TEST_FRONTEND_IMAGE: 'sesrag-ws-frontend:config-only',
    WS_TEST_TOOLS_IMAGE: 'sesrag-ws-tools:config-only', WS_TEST_POSTGRES_DB: 'sesrag_workspace',
    WS_TEST_POSTGRES_USER: 'sesrag', WS_TEST_POSTGRES_PASSWORD: 'synthetic-not-a-real-secret',
    WS_TEST_DATABASE_URL: 'postgresql+psycopg://sesrag:synthetic@postgres:5432/sesrag_workspace',
    WS_TEST_PROVIDER_CONTROL_TOKEN: 'synthetic-control', WS_TEST_MODEL_API_KEY: 'synthetic-model-key',
  });
  return JSON.parse(execFileSync('docker', ['compose', '--env-file', path.join(SUITE_ROOT, 'compose/.env.workspace-test.example'),
    '--project-directory', REPO_ROOT, '-f', path.join(SUITE_ROOT, 'compose/docker-compose.workspace-test.yml'),
    '-p', 'sesrag-ws-config-only', '--profile', 'tools', 'config', '--format', 'json'], { env, encoding: 'utf8', windowsHide: true }));
}

test('Compose 所有服务沿用本分类标签，数据和端口均隔离', () => {
  const model = config();
  for (const [name, service] of Object.entries(model.services)) {
    assert.equal(service.labels['io.sesrag.test.category'], 'session', `${name} 分类标签不可固定 env`);
    assert.equal(service.labels['io.sesrag.test.owner'], 'synthetic-owner');
    assert.equal(service.container_name, undefined);
    for (const port of service.ports ?? []) {
      assert.equal(port.host_ip, '127.0.0.1'); assert.equal(String(port.published), '0');
    }
  }
  assert.equal(model.services.postgres.ports, undefined);
  assert.equal(model.services.redis.ports, undefined);
  assert.ok(model.services.postgres.command.join(' ').includes('cluster_name=sesrag-ws-abcdef12-env'));
});

test('Compose 明确迁移/Profile前置以及 Worker 独立就绪观测', () => {
  const { services } = config();
  assert.equal(services['profile-init'].depends_on.migrate.condition, 'service_completed_successfully');
  for (const name of ['api', 'worker']) assert.equal(services[name].depends_on['profile-init'].condition, 'service_completed_successfully');
  assert.ok(services.worker.healthcheck.test.join(' ').includes('worker_count'));
  assert.ok(services.tools.build.args.APP_IMAGE.includes('sesrag-ws-app:'));
});

test('PowerShell 唯一入口与安装入口存在且可被 PowerShell 7 解析', () => {
  for (const name of ['run-workspace-tests.ps1', 'setup-tools.ps1']) {
    const target = path.join(SUITE_ROOT, name);
    assert.ok(fs.existsSync(target), `${name} 不存在`);
    const script = `$e=$null; $t=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('${target.replaceAll("'", "''")}',[ref]$t,[ref]$e); if($e.Count){$e|Out-String; exit 1}`;
    execFileSync('pwsh', ['-NoProfile', '-Command', script], { encoding: 'utf8', windowsHide: true });
  }
});

test('源码指纹覆盖前端契约生成脚本', () => {
  const files = buildSourceManifest().files.map(({ path: file }) => file);
  assert.ok(files.includes('frontend/scripts/generate-api-types.mjs'));
  assert.ok(files.includes('tests/sesrag-persistent-session-workspace-test/fixtures/documents/history-sentinel.md'));
  assert.ok(!files.includes('tests/sesrag-persistent-session-workspace-test/环境实施与验证记录.md'));
});

test('前端镜像依赖安装使用锁文件和有界网络重试，不丢弃已下载缓存', () => {
  const dockerfile = fs.readFileSync(path.join(REPO_ROOT, 'docker/frontend/Dockerfile'), 'utf8');
  assert.match(dockerfile, /--mount=type=cache,id=sesrag-frontend-npm,target=\/root\/\.npm/);
  assert.match(dockerfile, /npm ci\b/);
  assert.match(dockerfile, /--maxsockets=5/);
  assert.match(dockerfile, /--fetch-retries=3/);
  assert.match(dockerfile, /--fetch-timeout=120000/);
  assert.doesNotMatch(dockerfile, /--force|--legacy-peer-deps/);
});

test('安装入口拒绝缓存祖先链接，不能清除链接外的既有文件', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-setup-guard-'));
  const suite = path.join(root, 'suite');
  const external = path.join(root, 'external');
  fs.mkdirSync(path.join(external, 'setup-tmp'), { recursive: true });
  fs.mkdirSync(path.join(suite, 'node_modules/playwright'), { recursive: true });
  const marker = path.join(external, 'setup-tmp/keep.txt');
  fs.writeFileSync(marker, '外部既有文件不可删除');
  fs.copyFileSync(path.join(SUITE_ROOT, 'setup-tools.ps1'), path.join(suite, 'setup-tools.ps1'));
  fs.writeFileSync(path.join(suite, 'node_modules/playwright/cli.js'), 'process.exit(23);');
  try {
    try { fs.symlinkSync(external, path.join(suite, '.cache'), process.platform === 'win32' ? 'junction' : 'dir'); }
    catch { t.skip('宿主不允许创建目录链接'); return; }
    assert.throws(() => execFileSync('pwsh', ['-NoProfile', '-File', path.join(suite, 'setup-tools.ps1')],
      { encoding: 'utf8', windowsHide: true, stdio: 'pipe' }));
    assert.equal(fs.readFileSync(marker, 'utf8'), '外部既有文件不可删除');
    assert.equal(fs.readdirSync(external).length, 1);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
