// 临时下载恢复工具：只为TEST-002缓存官方固定revision资产，交由原安装器完成安装。
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { once } from 'node:events';

const repo = 'D:/Agentic_RAG/SesRAG';
const suite = path.join(repo, 'tests/sesrag-persistent-session-workspace-test');
const cache = path.join(suite, '.cache/browser-rescue');
const chunkSize = 2 * 1024 * 1024;
const workers = 12;
const assets = [
  {
    name: 'chrome-win64.zip',
    url: 'https://storage.googleapis.com/chrome-for-testing-public/156.0.8078.4/win64/chrome-win64.zip',
    route: '/builds/cft/156.0.8078.4/win64/chrome-win64.zip',
    bytes: 207073013,
    md5: 'wFMwF9jLOtX7TYabJv5FLw==',
  },
  {
    name: 'chrome-headless-shell-win64.zip',
    url: 'https://storage.googleapis.com/chrome-for-testing-public/156.0.8078.4/win64/chrome-headless-shell-win64.zip',
    route: '/builds/cft/156.0.8078.4/win64/chrome-headless-shell-win64.zip',
    bytes: 123826519,
    md5: 'rT33sBjoEAhkmSHMEEwqdA==',
  },
  {
    name: 'ffmpeg-win64.zip',
    url: 'https://cdn.playwright.dev/builds/ffmpeg/1013/ffmpeg-win64.zip',
    route: '/builds/ffmpeg/1013/ffmpeg-win64.zip',
    bytes: 1663577,
    md5: 'bfdtScv/FyTs23Q/J3HU7w==',
  },
  {
    name: 'winldd-win64.zip',
    url: 'https://cdn.playwright.dev/builds/winldd/1007/winldd-win64.zip',
    route: '/builds/winldd/1007/winldd-win64.zip',
    bytes: 128684,
    md5: 'ZEKUUFqmhNESWSoHKQynPw==',
  },
];

fs.mkdirSync(cache, { recursive: true });
const activeChildren = new Set();
let cancelling = false;

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: repo, windowsHide: true, ...options });
    activeChildren.add(child);
    let output = '';
    child.stdout?.on('data', value => {
      output += value;
      if (options.forward) process.stdout.write(value);
    });
    child.stderr?.on('data', value => {
      output += value;
      if (options.forward) process.stderr.write(value);
    });
    child.on('error', error => {
      activeChildren.delete(child);
      reject(error);
    });
    child.on('exit', code => {
      activeChildren.delete(child);
      if (code === 0) resolve(output);
      else reject(new Error(`${path.basename(command)} failed with exit ${code}`));
    });
  });
}

async function hashes(filename) {
  const md5 = createHash('md5');
  const sha256 = createHash('sha256');
  for await (const data of fs.createReadStream(filename)) {
    md5.update(data);
    sha256.update(data);
  }
  return { md5: md5.digest('base64'), sha256: sha256.digest('hex') };
}

function readHeaders(filename) {
  const text = fs.readFileSync(filename, 'utf8').replace(/\r/g, '');
  const blocks = text.trim().split('\n\n');
  const final = blocks.at(-1);
  const fields = new Map();
  for (const line of final.split('\n').slice(1)) {
    const index = line.indexOf(':');
    if (index >= 0) {
      const name = line.slice(0, index).toLowerCase();
      fields.set(name, [fields.get(name), line.slice(index + 1).trim()].filter(Boolean).join(','));
    }
  }
  return { status: Number(final.match(/^HTTP\/[\d.]+ (\d+)/)?.[1]), fields };
}

async function prepare(asset) {
  if (cancelling) throw new Error('download cancelled');
  const filename = path.join(cache, asset.name);
  const headerFile = filename + '.official-headers';
  await run('curl.exe', [
    '--silent', '--show-error', '--fail', '--location', '--head',
    '--connect-timeout', '10', '--max-time', '45', '--output', headerFile, asset.url,
  ]);
  const { status, fields } = readHeaders(headerFile);
  const officialMd5 = fields.get('content-md5') ?? fields.get('x-goog-hash')?.match(/md5=([^,]+)/)?.[1];
  if (status !== 200 || Number(fields.get('content-length')) !== asset.bytes || officialMd5 !== asset.md5)
    throw new Error(`${asset.name}: official metadata changed; refusing download`);

  if (fs.existsSync(filename) && fs.statSync(filename).size === asset.bytes) {
    const found = await hashes(filename);
    if (found.md5 === asset.md5) return { ...asset, ...found, filename };
  }

  const partDir = path.join(cache, asset.name + '.parts');
  fs.mkdirSync(partDir, { recursive: true });
  const parts = Array.from({ length: Math.ceil(asset.bytes / chunkSize) }, (_, index) => {
    const start = index * chunkSize;
    const end = Math.min(asset.bytes - 1, start + chunkSize - 1);
    return { index, start, end, filename: path.join(partDir, String(index).padStart(4, '0') + '.part') };
  });
  let next = 0;
  let completed = 0;
  let lastProgress = 0;
  async function worker() {
    while (!cancelling) {
      const part = parts[next++];
      if (!part) return;
      const expectedBytes = part.end - part.start + 1;
      if (!fs.existsSync(part.filename) || fs.statSync(part.filename).size !== expectedBytes) {
        let error;
        for (let attempt = 1; attempt <= 3; attempt++) {
          try {
            await run('curl.exe', [
              '--silent', '--show-error', '--fail', '--location', '--http1.1',
              '--connect-timeout', '10', '--max-time', '75', '--speed-limit', '1024', '--speed-time', '20',
              '--range', `${part.start}-${part.end}`, '--dump-header', part.filename + '.headers',
              '--output', part.filename + '.downloading', asset.url,
            ]);
            const response = readHeaders(part.filename + '.headers');
            const range = `bytes ${part.start}-${part.end}/${asset.bytes}`;
            if (response.status !== 206 || response.fields.get('content-range') !== range ||
                fs.statSync(part.filename + '.downloading').size !== expectedBytes)
              throw new Error(`${asset.name}: range response failed validation`);
            fs.renameSync(part.filename + '.downloading', part.filename);
            error = null;
            break;
          } catch (failure) {
            error = failure;
          }
        }
        if (error) throw error;
      }
      completed++;
      if (Date.now() - lastProgress > 15000 || completed === parts.length) {
        console.log(`${asset.name}: ${completed}/${parts.length} verified ranges`);
        lastProgress = Date.now();
      }
    }
  }
  const results = await Promise.allSettled(Array.from({ length: Math.min(workers, parts.length) }, worker));
  const failure = results.find(result => result.status === 'rejected');
  if (failure) throw failure.reason;
  if (cancelling) throw new Error('download cancelled');

  const assembled = filename + '.assembling';
  const output = fs.createWriteStream(assembled);
  for (const part of parts) {
    for await (const data of fs.createReadStream(part.filename)) {
      if (!output.write(data)) await once(output, 'drain');
    }
  }
  output.end();
  await once(output, 'finish');
  const found = await hashes(assembled);
  if (fs.statSync(assembled).size !== asset.bytes || found.md5 !== asset.md5)
    throw new Error(`${asset.name}: combined artifact digest failed validation`);
  fs.renameSync(assembled, filename);
  console.log(`${asset.name}: MD5 and length match official metadata; SHA256 ${found.sha256}`);
  return { ...asset, ...found, filename };
}

let localServer;
try {
  const prepared = [];
  // 两个大文件顺序下载，限制同时连接数；单个文件内部只开有限分段并发。
  for (const asset of assets) prepared.push(await prepare(asset));
  fs.writeFileSync(path.join(cache, 'verified-assets.json'), JSON.stringify(prepared, null, 2) + '\n');
  const routes = new Map(prepared.map(asset => [asset.route, asset]));
  localServer = http.createServer((request, response) => {
    const asset = routes.get(request.url);
    if (!asset || !['GET', 'HEAD'].includes(request.method)) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { 'Content-Length': asset.bytes, 'Content-Type': 'application/zip' });
    if (request.method === 'HEAD') response.end();
    else fs.createReadStream(asset.filename).pipe(response);
  });
  localServer.listen(0, '127.0.0.1');
  await once(localServer, 'listening');
  const origin = `http://127.0.0.1:${localServer.address().port}`;
  console.log('Verified loopback asset cache ready; running the original suite setup entrypoint.');
  await run('pwsh.exe', ['-NoProfile', '-File', path.join(suite, 'setup-tools.ps1')], {
    forward: true,
    env: {
      ...process.env,
      PLAYWRIGHT_DOWNLOAD_HOST: origin,
      PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST: origin,
      PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT: '120000',
    },
  });
  console.log('Suite setup entrypoint completed successfully.');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  cancelling = true;
  if (localServer) {
    localServer.closeAllConnections();
    await new Promise(resolve => localServer.close(resolve));
  }
  for (const child of activeChildren) child.kill();
  console.log('Temporary download children and loopback cache service closed.');
}
