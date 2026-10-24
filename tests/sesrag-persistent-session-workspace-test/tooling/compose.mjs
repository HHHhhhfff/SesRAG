import path from 'node:path';
import { REPO_ROOT, SUITE_ROOT } from './preflight.mjs';
import { docker, runPath } from './resources.mjs';

export const COMPOSE_FILE = path.join(SUITE_ROOT, 'compose/docker-compose.workspace-test.yml');
export function composeArgs(session, project, args) {
  const envFile = path.join(runPath('runtime', session.run_id), 'compose.env');
  return ['compose', '--env-file', envFile, '--project-directory', REPO_ROOT, '-f', COMPOSE_FILE, '--project-name', project, ...args];
}
export function runCompose(session, project, args, options = {}) {
  return docker(composeArgs(session, project, args), options);
}
export async function waitService(session, project, service, mode, timeoutSeconds = 300) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  let last = 'unknown';
  while (Date.now() < deadline) {
    const ids = (await runCompose(session, project, ['ps', '-a', '-q', service])).split(/\r?\n/).filter(Boolean);
    if (ids.length) {
      const state = JSON.parse(await docker(['inspect', '--format', '{{json .State}}', ids[0]]));
      last = state.Status + (state.Health ? `/${state.Health.Status}` : '');
      if (mode === 'healthy' && state.Status === 'running' && state.Health?.Status === 'healthy') return ids[0];
      if (mode === 'exited' && state.Status === 'exited') return { id: ids[0], exit_code: state.ExitCode };
      if (state.Status === 'exited' && mode !== 'exited') throw new Error(`${service} 意外退出，退出码 ${state.ExitCode}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  throw new Error(`${service} 等待${mode === 'healthy' ? '健康' : '退出'}超时，最近状态 ${last}`);
}
export async function publishedPort(session, project, service, target) {
  const value = await runCompose(session, project, ['port', service, String(target)]);
  const match = value.match(/^127\.0\.0\.1:(\d+)$/m);
  if (!match) throw new Error(`${service}:${target} 未绑定到可确认的 127.0.0.1 动态端口`);
  return Number(match[1]);
}
