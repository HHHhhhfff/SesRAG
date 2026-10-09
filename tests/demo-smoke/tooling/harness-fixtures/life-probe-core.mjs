import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

// LIFE_004：仅固定harness manifest调用这些工具哨兵，永远不作为产品断言或正式分类。
export async function probe(mode) {
  const args = {};
  for (let index = 2; index < process.argv.length; index += 2) args[process.argv[index].slice(1)] = process.argv[index + 1];
  const keys = ['BaseUrl', 'FrontendUrl', 'RunId', 'ArtifactDir', 'RuntimeDir', 'FixtureDir'];
  if (!keys.every(key => typeof args[key] === 'string' && args[key].length) || Object.keys(args).length !== 6) throw new Error('LIFE_004 六固定参数不完整');
  const category = `life-${mode}`;
  const data = { schema_version: 1, run_id: args.RunId, category, status: 'passed', started_at: new Date().toISOString(), finished_at: new Date().toISOString(), checks: [{ id: 'LIFE_004__TP-LIFE-003__harness_probe', test_point_id: 'TP-LIFE-003', status: 'passed', expected: '工具哨兵接收六固定参数并验证真实runtime/fixture', actual: '六参数和路径均合法；不是产品验收', evidence: [] }], evidence: [] };
  const context = JSON.parse(fs.readFileSync(path.join(args.RuntimeDir, 'context.json'), 'utf8').replace(/^\uFEFF/, ''));
  if (context.run_id !== args.RunId || !fs.existsSync(path.join(args.FixtureDir, 'upload-safe', 'smoke.docx'))) throw new Error('LIFE_004 参数身份或fixture错误');
  if (args.BaseUrl !== `http://127.0.0.1:${context.api_port}` || args.FrontendUrl !== `http://127.0.0.1:${context.frontend_port}` || path.basename(args.ArtifactDir) !== args.RunId || path.basename(args.RuntimeDir) !== args.RunId) throw new Error('LIFE_004 地址或报告目录六参数不一致');
  console.log(`LIFE_004 工具哨兵 ${category} 收到六固定参数；run_id=${args.RunId}`);
  if (mode === 'missing-report') return;
  if (mode === 'timeout') {
    // LIFE_004：子进程仍在自身树内，运行器超时须递归终止；仅记PID用于结束后只读核对。
    const child = spawn(process.execPath, ['-e', `globalThis.lifeOwnedRunId=${JSON.stringify(args.RunId)};setInterval(()=>{},1000)`], { windowsHide: true, stdio: 'ignore' });
    const marker = { parent_pid: process.pid, child_pid: child.pid, run_id: args.RunId };
    fs.writeFileSync(path.join(args.ArtifactDir, 'environment', 'life-timeout-pids.json'), JSON.stringify(marker), 'utf8');
    fs.writeFileSync(path.join(args.RuntimeDir, 'life-timeout-pids.json'), JSON.stringify(marker), 'utf8');
    await new Promise(resolve => setTimeout(resolve, 60000));
    return;
  }
  if (mode === 'empty-passed') data.checks = [];
  if (mode === 'wrong-run') data.run_id = 'harness-wrong-run';
  if (mode === 'wrong-category') data.category = 'life-wrong-target';
  if (mode === 'blocked') { data.status = 'blocked'; data.checks[0].status = 'blocked'; data.checks[0].actual = '工具哨兵明确blocked，运行器不能误判通过'; }
  fs.writeFileSync(path.join(args.ArtifactDir, 'categories', `${category}.json`), JSON.stringify(data), 'utf8');
  if (mode === 'nonzero') process.exitCode = 7;
}
