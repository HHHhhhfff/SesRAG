import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

const SOURCE = 'a'.repeat(64);
const RUN = 'ws-20261021t010203z-a1b2c3d4';
const NEXT_RUN = 'ws-20261021t020304z-b1c2d3e4';
const NAMES = ['app', 'frontend', 'tools'];
const sha256 = (value) => crypto.createHash('sha256').update(value).digest('hex');

function workspace(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sesrag-frozen-selftest-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

// 测试归档按POSIX tar字段独立构造，不调用真实Docker或系统归档工具。
function tarArchive(files) {
  const chunks = [];
  for (const [name, value] of Object.entries(files)) {
    const content = Buffer.from(value);
    const header = Buffer.alloc(512);
    header.write(name, 0, 100);
    header.write('0000600\0', 100, 8);
    header.write('0000000\0', 108, 8);
    header.write('0000000\0', 116, 8);
    header.write(`${content.length.toString(8).padStart(11, '0')}\0`, 124, 12);
    header.write('00000000000\0', 136, 12);
    header.fill(32, 148, 156);
    header.write('0', 156, 1);
    header.write('ustar\0', 257, 6);
    header.write('00', 263, 2);
    const checksum = [...header].reduce((sum, byte) => sum + byte, 0);
    header.write(`${checksum.toString(8).padStart(6, '0')}\0 `, 148, 8);
    chunks.push(header, content, Buffer.alloc((512 - content.length % 512) % 512));
  }
  return Buffer.concat([...chunks, Buffer.alloc(1024)]);
}

function fixture(runId = RUN) {
  const configs = new Map(NAMES.map((name) => {
    const content = JSON.stringify({ architecture: 'amd64', os: 'linux', fixture_name: name,
      rootfs: { type: 'layers', diff_ids: [] }, config: { Labels: {
        'io.sesrag.test.suite': 'workspace-test', 'io.sesrag.test.source': SOURCE,
      } } });
    return [`sha256:${sha256(content)}`, content];
  }));
  const ids = [...configs.keys()];
  const session = {
    run_id: runId,
    source_before: { source_digest: SOURCE, files: [
      { path: 'pyproject.toml', sha256: '1'.repeat(64) },
      { path: 'frontend/package-lock.json', sha256: '2'.repeat(64) },
    ] },
    images: NAMES.map((name, i) => ({ name, tag: `sesrag-ws-${name}:${runId}`, id: ids[i] })),
    dependencies: { python_version: '3.12.14', node_version: process.versions.node,
      packages: [{ name: 'pytest', version: '8.4.2' }, { name: 'psycopg', version: '3.2.6' }],
      private_value: 'PRIVATE_SENTINEL' },
    secret_values: ['DO_NOT_COPY_SESSION_SECRET'],
  };
  const state = { calls: [], tags: new Map(session.images.map(({ tag, id }) => [tag, id])),
    present: new Set(ids), wrongIdentity: null, wrongSource: false, failSave: false };
  const archive = (tags = null) => tarArchive({
    ...Object.fromEntries([...configs].map(([id, content]) => [`${id.slice(7)}.json`, content])),
    'manifest.json': JSON.stringify(ids.map((id) => ({ Config: `${id.slice(7)}.json`, RepoTags: tags, Layers: [] }))),
  });
  const docker = async (args, options) => {
    state.calls.push({ args, options });
    if (args[0] !== 'image') throw new Error('自测禁止调用未登记Docker命令');
    if (args[1] === 'inspect') {
      const reference = args.at(-1);
      const id = state.wrongIdentity ?? state.tags.get(reference) ?? reference;
      if (!state.present.has(id)) throw new Error('image not found');
      return JSON.stringify({ id, repo_digests: [], suite: 'workspace-test', source: state.wrongSource ? 'b'.repeat(64) : SOURCE });
    }
    if (args[1] === 'save') {
      assert.equal(args[2], '--output');
      assert.deepEqual(args.slice(4), ids);
      fs.writeFileSync(args[3], state.failSave ? 'partial' : archive());
      if (state.failSave) throw new Error('PRIVATE_DOCKER_ERROR');
      return '';
    }
    if (args[1] === 'load') {
      assert.equal(args[2], '--input');
      state.present = new Set(ids);
      return 'Loaded image IDs';
    }
    if (args[1] === 'tag') {
      state.tags.set(args[3], args[2]);
      return '';
    }
    if (args[1] === 'ls') return state.tags.get(args.at(-1)) ?? '';
    throw new Error('自测禁止调用未登记Docker命令');
  };
  return { session, state, docker, ids, archive };
}

async function moduleUnderTest() {
  return import('./frozen-builds.mjs');
}

test('Docker29 OCI index身份沿descriptor验证config，不误判config摘要与index摘要不同', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest(); const original = fixture(); const files = {}; const roots = [];
  const metadata = new Map(); const legacy = JSON.parse(JSON.stringify(original.session.images));
  for (const item of original.session.images) {
    const config = JSON.stringify({ config: { Labels: { 'io.sesrag.test.suite': 'workspace-test' } }, rootfs: { diff_ids: [] } });
    const configId = `sha256:${sha256(config)}`; files[`blobs/sha256/${configId.slice(7)}`] = config;
    const image = JSON.stringify({ schemaVersion: 2, config: { digest: configId, size: Buffer.byteLength(config) }, layers: [] });
    const imageId = `sha256:${sha256(image)}`; files[`blobs/sha256/${imageId.slice(7)}`] = image;
    const index = JSON.stringify({ schemaVersion: 2, manifests: [{ digest: imageId, size: Buffer.byteLength(image) }], fixture: item.name });
    item.id = `sha256:${sha256(index)}`; files[`blobs/sha256/${item.id.slice(7)}`] = index;
    roots.push({ digest: item.id, size: Buffer.byteLength(index) }); metadata.set(item.tag, item.id);
  }
  files['index.json'] = JSON.stringify({ schemaVersion: 2, manifests: roots });
  const configPath = Object.keys(files).find((name) => name.startsWith('blobs/') && JSON.parse(files[name]).rootfs);
  files['manifest.json'] = JSON.stringify([{ Config: configPath, RepoTags: null, Layers: [] }]);
  const docker = async (args, options) => {
    if (args[1] === 'save') { fs.writeFileSync(args[3], tarArchive(files)); return ''; }
    if (args[1] === 'inspect') return JSON.stringify({ id: metadata.get(args.at(-1)), repo_digests: [], suite: 'workspace-test', source: SOURCE });
    return original.docker(args, options);
  };
  const result = await saveFrozenBuild(original.session, { docker, cacheRoot: workspace(t) });
  assert.equal(result.manifest.images.length, 3); assert.notDeepEqual(original.session.images.map((item) => item.id), legacy.map((item) => item.id));
});

test('按镜像ID冻结并恢复相同ID，仅创建本轮tag且不保存秘密', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t);
  const original = fixture();
  const saved = await saveFrozenBuild(original.session, { docker: original.docker, cacheRoot });
  assert.match(saved.fingerprint, /^[a-f0-9]{64}$/);
  const directory = path.join(cacheRoot, saved.fingerprint);
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'manifest.json'), 'utf8'));
  assert.equal(manifest.archive.sha256, sha256(fs.readFileSync(path.join(directory, 'images.tar'))));
  assert.equal(manifest.schema_version, 1);
  assert.ok(!JSON.stringify(manifest).includes(RUN));
  assert.ok(!JSON.stringify(manifest).includes('PRIVATE_SENTINEL'));
  assert.ok(!JSON.stringify(manifest).includes('DO_NOT_COPY_SESSION_SECRET'));
  const next = fixture(NEXT_RUN).session;
  next.images.forEach((item) => { item.id = null; });
  delete next.dependencies;
  original.state.tags.clear(); original.state.present.clear();
  const loaded = await loadFrozenBuild(next, saved.fingerprint, { docker: original.docker, cacheRoot });
  assert.equal(loaded.fingerprint, saved.fingerprint);
  assert.deepEqual(next.images.map(({ id }) => id), original.ids);
  assert.deepEqual([...original.state.tags.keys()], NAMES.map((name) => `sesrag-ws-${name}:${NEXT_RUN}`));
  assert.deepEqual(next.dependencies.packages, [{ name: 'psycopg', version: '3.2.6' }, { name: 'pytest', version: '8.4.2' }]);
  assert.ok(original.state.calls.every(({ options }) => options.timeoutMs > 0 && options.timeoutMs <= 1800000));
  assert.ok(original.state.calls.filter(({ args }) => args[1] === 'inspect').every(({ args }) => !args.includes('{{json .}}') && !args.join(' ').includes('Env')));
});

test('重复保存校验现有归档而不再次导出或覆盖', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const first = await saveFrozenBuild(session, { docker, cacheRoot });
  const file = path.join(cacheRoot, first.fingerprint, 'images.tar');
  const before = fs.readFileSync(file);
  const second = await saveFrozenBuild(session, { docker, cacheRoot });
  assert.equal(second.fingerprint, first.fingerprint);
  assert.deepEqual(fs.readFileSync(file), before);
  assert.equal(state.calls.filter(({ args }) => args[1] === 'save').length, 1);
});

test('源码变化在载入前拒绝且不静默构建', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  session.source_before.source_digest = 'b'.repeat(64);
  state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /SOURCE_MISMATCH/);
  assert.equal(state.calls.length, 0);
});

test('归档篡改在载入前拒绝', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  fs.appendFileSync(path.join(cacheRoot, saved.fingerprint, 'images.tar'), 'tampered');
  state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /ARCHIVE_MISMATCH/);
  assert.equal(state.calls.length, 0);
});

for (const value of ['', '../escape', '/arbitrary/path', 'A'.repeat(64), `${'a'.repeat(64)}/..`]) {
  test(`拒绝非法FrozenBuild指纹 ${JSON.stringify(value)}`, async (t) => {
    const { loadFrozenBuild } = await moduleUnderTest();
    const { session, state, docker } = fixture();
    await assert.rejects(loadFrozenBuild(session, value, { docker, cacheRoot: workspace(t) }), /FINGERPRINT_INVALID/);
    assert.equal(state.calls.length, 0);
  });
}

for (const missing of ['manifest.json', 'images.tar']) {
  test(`缺少${missing}不允许载入或重建`, async (t) => {
    const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
    const cacheRoot = workspace(t); const { session, state, docker } = fixture();
    const saved = await saveFrozenBuild(session, { docker, cacheRoot });
    fs.unlinkSync(path.join(cacheRoot, saved.fingerprint, missing)); state.calls.length = 0;
    await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /CACHE_INCOMPLETE/);
    assert.equal(state.calls.length, 0);
  });
}

test('镜像tag不再指向登记ID时拒绝导出', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const { session, state, docker, ids } = fixture();
  state.tags.set(session.images[0].tag, ids[1]);
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot: workspace(t) }), /IMAGE_ID_MISMATCH/);
  assert.equal(state.calls.filter(({ args }) => args[1] === 'save').length, 0);
});

test('显式登记的不同镜像ID不能被load覆盖', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  session.images[0].id = `sha256:${'b'.repeat(64)}`; state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /IMAGE_ID_MISMATCH/);
  assert.equal(state.calls.length, 0);
});

test('恢复镜像实际ID或来源标签不符时拒绝挂tag', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker, ids } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  state.wrongIdentity = ids[1]; state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /IMAGE_ID_MISMATCH/);
  assert.equal(state.calls.filter(({ args }) => args[1] === 'tag').length, 0);
});

test('即使归档hash重写也拒绝归档恢复旧run tag', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker, archive } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  const directory = path.join(cacheRoot, saved.fingerprint);
  const malicious = archive([`sesrag-ws-app:${RUN}`]);
  fs.writeFileSync(path.join(directory, 'images.tar'), malicious);
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'manifest.json'), 'utf8'));
  manifest.archive.sha256 = sha256(malicious); manifest.archive.bytes = malicious.length;
  fs.writeFileSync(path.join(directory, 'manifest.json'), JSON.stringify(manifest));
  state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /ARCHIVE_TAGS_REJECTED/);
  assert.equal(state.calls.length, 0);
});

test('导出失败只清除本次新建目录且不泄露驱动错误', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  fs.mkdirSync(path.join(cacheRoot, 'retained')); state.failSave = true;
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot }), (error) => {
    assert.match(error.message, /FROZEN_SAVE_FAILED/);
    assert.ok(!error.message.includes('PRIVATE_DOCKER_ERROR')); return true;
  });
  assert.deepEqual(fs.readdirSync(cacheRoot), ['retained']);
});

test('拒绝符号链接缓存根目录', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const root = workspace(t); const real = path.join(root, 'real'); const link = path.join(root, 'link');
  fs.mkdirSync(real);
  try { fs.symlinkSync(real, link, process.platform === 'win32' ? 'junction' : 'dir'); }
  catch { t.skip('当前宿主不允许创建目录链接'); return; }
  const { session, state, docker } = fixture();
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot: link }), /CACHE_PATH_REJECTED/);
  assert.equal(state.calls.length, 0);
});

test('缺少镜像ID和未知镜像名称不能冻结', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const { session, state, docker } = fixture();
  session.images[0].id = null;
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot: workspace(t) }), /IMAGE_RECORD_INVALID/);
  session.images[0].name = 'development';
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot: workspace(t) }), /IMAGE_RECORD_INVALID/);
  assert.equal(state.calls.length, 0);
});

test('拒绝覆盖已指向其他镜像的本轮tag', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker, ids } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  state.tags.set(session.images[0].tag, ids[1]); state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /IMAGE_TAG_CONFLICT/);
  assert.equal(state.calls.filter(({ args }) => args[1] === 'load' || args[1] === 'tag').length, 0);
});

test('部署依赖与冻结记录不一致时在load前拒绝', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  session.dependencies.packages[0].version = '99.0'; state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /DEPENDENCY_MISMATCH/);
  assert.equal(state.calls.length, 0);
});

test('缺少真实解析依赖记录不能冻结', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const { session, state, docker } = fixture(); delete session.dependencies;
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot: workspace(t) }), /DEPENDENCY_RECORD_INVALID/);
  assert.equal(state.calls.length, 0);
});

test('恢复镜像来源标签不匹配时不创建任何本轮tag', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  state.wrongSource = true; state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /IMAGE_SOURCE_MISMATCH/);
  assert.equal(state.calls.filter(({ args }) => args[1] === 'tag').length, 0);
});

test('缓存指纹目录为junction时拒绝载入', async (t) => {
  const { saveFrozenBuild, loadFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  const directory = path.join(cacheRoot, saved.fingerprint); const moved = path.join(cacheRoot, 'moved');
  fs.renameSync(directory, moved);
  try { fs.symlinkSync(moved, directory, process.platform === 'win32' ? 'junction' : 'dir'); }
  catch { t.skip('当前宿主不允许创建目录链接'); return; }
  state.calls.length = 0;
  await assert.rejects(loadFrozenBuild(session, saved.fingerprint, { docker, cacheRoot }), /CACHE_PATH_REJECTED/);
  assert.equal(state.calls.length, 0);
});

test('现有归档损坏时重复save拒绝修复覆盖', async (t) => {
  const { saveFrozenBuild } = await moduleUnderTest();
  const cacheRoot = workspace(t); const { session, state, docker } = fixture();
  const saved = await saveFrozenBuild(session, { docker, cacheRoot });
  const archiveFile = path.join(cacheRoot, saved.fingerprint, 'images.tar');
  fs.appendFileSync(archiveFile, 'corruption'); const corrupted = fs.readFileSync(archiveFile);
  await assert.rejects(saveFrozenBuild(session, { docker, cacheRoot }), /ARCHIVE_MISMATCH/);
  assert.deepEqual(fs.readFileSync(archiveFile), corrupted);
  assert.equal(state.calls.filter(({ args }) => args[1] === 'save').length, 1);
});
