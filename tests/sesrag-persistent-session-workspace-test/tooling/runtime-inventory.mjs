import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { SUITE_ROOT } from './preflight.mjs';
import { assertOwnership, docker as defaultDocker } from './resources.mjs';
import { runCommand } from './process-registry.mjs';

// 仅记录解析后的包名/版本，不保存pip配置、下载URL、环境全集或容器Env。
const pythonInventory = "import importlib.metadata,json,sys;print(json.dumps({'python_version':sys.version.split()[0],'packages':sorted([{'name':p.metadata['Name'],'version':p.version} for p in importlib.metadata.distributions()],key=lambda p:p['name'].lower())}))";

export function storageInventory(root = SUITE_ROOT) {
  const measure = (relative) => {
    const target = path.join(root, relative); let bytes = 0; let files = 0; let skippedLinks = 0;
    const visit = (entry) => {
      const stat = fs.lstatSync(entry);
      if (stat.isSymbolicLink()) { skippedLinks += 1; return; }
      if (stat.isDirectory()) for (const name of fs.readdirSync(entry)) visit(path.join(entry, name));
      else if (stat.isFile()) { bytes += stat.size; files += 1; }
    };
    if (fs.existsSync(target)) visit(target);
    return { bytes, files, skipped_links: skippedLinks };
  };
  return {
    measured_at: new Date().toISOString(),
    artifacts: measure('artifacts'), node_modules: measure('node_modules'),
    cache: measure('.cache'), frozen_builds: measure('.cache/frozen-builds'),
    browser_rescue: measure('.cache/browser-rescue'),
    docker_shared_cache: { bytes: null, reason: '共享基础镜像/构建缓存无法安全分摊到本轮，不执行全局清理。' },
  };
}

export async function runtimeInventory(session, project, { docker = defaultDocker, command = runCommand } = {}) {
  const result = { schema_version: 1, run_id: session.run_id, project, versions: {}, images: [], dependencies: {} };
  result.versions.node_host = process.versions.node;
  result.versions.compose = await docker(['compose', 'version', '--short']);
  const pwsh = await command('pwsh', ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()']);
  if (pwsh.code !== 0 || pwsh.timedOut || pwsh.truncated) throw new Error('PowerShell版本采集失败');
  result.versions.powershell = pwsh.stdout.trim();
  for (const service of ['api', 'provider', 'frontend']) {
    const ids = (await docker(['ps', '-aq', '--filter', `label=com.docker.compose.project=${project}`,
      '--filter', `label=com.docker.compose.service=${service}`])).split(/\r?\n/).filter(Boolean);
    if (ids.length !== 1) throw new Error('运行时清单要求唯一的已登记服务');
    const [container] = JSON.parse(await docker(['inspect', ids[0]]));
    assertOwnership(container.Config?.Labels, session, project);
    const [image] = JSON.parse(await docker(['image', 'inspect', container.Image]));
    result.images.push({ service, image_id: container.Image, repo_digests: image.RepoDigests ?? [] });
    if (service === 'frontend') result.versions.node_frontend = (await docker(['exec', ids[0], 'node', '--version'])).trim();
    else {
      const dependencies = JSON.parse(await docker(['exec', ids[0], 'python', '-c', pythonInventory]));
      result.dependencies[service === 'api' ? 'app' : 'tools'] = {
        ...dependencies, sha256: crypto.createHash('sha256').update(JSON.stringify(dependencies)).digest('hex'),
      };
    }
  }
  result.storage = storageInventory();
  return result;
}
