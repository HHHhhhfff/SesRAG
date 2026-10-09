import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { Context, parseArgs, assert, execute, smokeRoot, repoRoot, registerNestedRun } from '../../lib/category-kit.mjs';
import { readJson, deployedResources } from '../../specific_test_script/life-runner-driver.mjs';

// LIFE_006：这是运行器兜底工具哨兵；真实创建诊断子环境后故意等到分类超时，不自行恢复。
const ctx = new Context(parseArgs());
const project = ctx.context.compose_project;
const markerPath = path.join(ctx.args.ArtifactDir, 'environment', 'life-nested-deferred.json');
const marker = { schema_version: 1, parent_run_id: ctx.args.RunId, probe_pid: process.pid, phase: 'starting', child_state: null, child_exit_code: null, resources: null };
const saveMarker = () => fs.writeFileSync(markerPath, JSON.stringify(marker, null, 2), 'utf8');
saveMarker();
const child = spawn('pwsh', ['-NoProfile', '-File', path.join(smokeRoot, 'run-demo-smoke.ps1'), '-HarnessScenario', 'disabled', '-ProjectName', 'sesrag-demo-smoke-recovery', '-Build:$false', '-BackendImage', `${project}-backend:local`, '-FrontendImage', `${project}-frontend:local`, '-WaitTimeoutSeconds', '45', '-KeepContainers'], { cwd: repoRoot, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let pending = ''; let observerError; let timedOut = false;
child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8');
child.stderr.on('data', () => {});
child.stdout.on('data', chunk => {
  pending += chunk;
  const lines = pending.split(/\r?\n/); pending = lines.pop();
  for (const line of lines) {
    const match = line.match(/^Run: ([a-z0-9-]+)；project: (sesrag-demo-smoke-[a-z0-9-]+)$/);
    if (match && !marker.child_state) {
      try {
        const state = readJson(path.join(smokeRoot, 'runtime', match[1], 'context.json'));
        assert.equal(state.run_id, match[1]); assert.equal(state.compose_project, match[2]);
        // LIFE_006：收到身份即持久登记，Node被kill后仍由父runner校验并恢复。
        registerNestedRun(ctx, state);
        marker.child_state = state; marker.phase = 'registered'; saveMarker();
        console.log(`LIFE_006 已登记自有子环境run_id=${state.run_id}，project=${state.compose_project}`);
      } catch (error) { observerError ??= error; }
    }
  }
});
const timer = setTimeout(() => {
  timedOut = true;
  if (process.platform === 'win32') execute('taskkill', ['/PID', String(child.pid), '/T', '/F'], { timeoutMs: 10000 });
  else child.kill('SIGKILL');
}, 75000);
let code;
try { code = await new Promise((resolve, reject) => { child.on('error', reject); child.on('close', value => resolve(value ?? -1)); }); }
finally { clearTimeout(timer); }
assert.ok(!timedOut, 'LIFE_006 诊断子环境未在75秒内完成');
assert.ok(!observerError && marker.child_state, 'LIFE_006 子环境持久登记失败');
assert.equal(code, 5, 'LIFE_006 子环境必须真实完成为cleanup_deferred/5');
const childArtifact = path.join(smokeRoot, 'artifacts', marker.child_state.run_id);
const summary = readJson(path.join(childArtifact, 'summary.json'));
assert.equal(summary.status, 'cleanup_deferred'); assert.equal(summary.cleanup_status, 'deferred');
marker.child_exit_code = code; marker.phase = 'deferred_completed'; marker.resources = deployedResources(marker.child_state.compose_project); saveMarker();
assert.ok(marker.resources.containers.length > 0, 'LIFE_006 诊断子环境须真实保留容器');
console.log(`LIFE_006 子环境真实deferred/5且资源保留，哨兵等待分类90秒超时；run_id=${marker.child_state.run_id}`);
// LIFE_006：没有分类finally清理；唯一恢复责任留给父runner的nested-runs登记兜底。
await new Promise(resolve => setTimeout(resolve, 150000));
throw new Error('LIFE_006 分类运行器没有在90秒内终止哨兵');
