import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { SUITE_ROOT } from './preflight.mjs';
import { docker as defaultDocker } from './resources.mjs';

const NAMES = ['app', 'frontend', 'tools'];
const DIGEST = /^[a-f0-9]{64}$/;
const IMAGE_ID = /^sha256:[a-f0-9]{64}$/;
const RUN_ID = /^ws-[0-9]{8}t[0-9]{6}z-[a-f0-9]{8}$/;
const VERSION = 'workspace-frozen-build-v1';
const CACHE_ROOT = path.join(SUITE_ROOT, '.cache/frozen-builds');
const LOCK_FILES = new Set(['pyproject.toml', 'frontend/package-lock.json',
  'tests/sesrag-persistent-session-workspace-test/package-lock.json',
  'tests/sesrag-persistent-session-workspace-test/requirements-tools.txt']);
const INSPECT = '{"id":{{json .Id}},"repo_digests":{{json .RepoDigests}},"suite":{{json (index .Config.Labels "io.sesrag.test.suite")}},"source":{{json (index .Config.Labels "io.sesrag.test.source")}}}';
const COMMAND_OPTIONS = { timeoutMs: 30000, maxBytes: 65536 };
const TRANSFER_OPTIONS = { timeoutMs: 1800000, maxBytes: 65536 };

class FrozenBuildError extends Error {
  constructor(code) { super(code); this.name = 'FrozenBuildError'; this.code = code; }
}
function requireCondition(condition, code) { if (!condition) throw new FrozenBuildError(code); }
function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
function digest(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function keysExactly(value, names) {
  return object(value) && Object.keys(value).sort().join('|') === [...names].sort().join('|');
}

function normalizeDependencies(value) {
  requireCondition(object(value) && typeof value.python_version === 'string'
    && /^[0-9]+\.[0-9]+\.[0-9]+(?:[a-z0-9.+-]*)$/i.test(value.python_version)
    && Array.isArray(value.packages) && value.packages.length > 0 && value.packages.length <= 10000,
  'DEPENDENCY_RECORD_INVALID');
  const names = new Set();
  const packages = value.packages.map((item) => {
    requireCondition(object(item) && typeof item.name === 'string' && typeof item.version === 'string'
      && /^[a-z0-9][a-z0-9._-]{0,199}$/i.test(item.name)
      && /^[a-z0-9][a-z0-9.+!_-]{0,127}$/i.test(item.version), 'DEPENDENCY_RECORD_INVALID');
    const name = item.name.toLowerCase().replace(/[-_.]+/g, '-');
    requireCondition(!names.has(name), 'DEPENDENCY_RECORD_INVALID'); names.add(name);
    return { name, version: item.version };
  }).sort((a, b) => a.name.localeCompare(b.name, 'en'));
  const normalized = { python_version: value.python_version, packages };
  if (value.node_version !== undefined) {
    requireCondition(typeof value.node_version === 'string' && /^\d+\.\d+\.\d+$/.test(value.node_version), 'DEPENDENCY_RECORD_INVALID');
    normalized.node_version = value.node_version;
  }
  return normalized;
}

function sessionImages(session, requireIds) {
  requireCondition(object(session) && RUN_ID.test(session.run_id ?? '')
    && Array.isArray(session.images) && session.images.length === 3, 'IMAGE_RECORD_INVALID');
  const result = NAMES.map((name) => {
    const matches = session.images.filter((item) => item?.name === name);
    requireCondition(matches.length === 1, 'IMAGE_RECORD_INVALID');
    const item = matches[0];
    requireCondition(item.tag === `sesrag-ws-${name}:${session.run_id}`
      && ((!requireIds && (item.id === null || item.id === undefined)) || IMAGE_ID.test(item.id ?? '')),
    'IMAGE_RECORD_INVALID');
    return item;
  });
  return result;
}

function sourceDigest(session) {
  const value = session?.source_before?.source_digest;
  requireCondition(typeof value === 'string' && DIGEST.test(value), 'SOURCE_RECORD_INVALID');
  return value;
}

function sourceFiles(session) {
  const result = (session.source_before.files ?? []).filter((item) => LOCK_FILES.has(item?.path))
    .map(({ path: file, sha256 }) => {
      requireCondition(DIGEST.test(sha256 ?? ''), 'SOURCE_RECORD_INVALID');
      return { path: file, sha256 };
    }).sort((a, b) => a.path.localeCompare(b.path, 'en'));
  requireCondition(new Set(result.map((item) => item.path)).size === result.length, 'SOURCE_RECORD_INVALID');
  return result;
}

function noLinks(target) {
  for (let current = path.resolve(target); ; current = path.dirname(current)) {
    try { requireCondition(!fs.lstatSync(current).isSymbolicLink(), 'CACHE_PATH_REJECTED'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (current === path.dirname(current)) break;
  }
}

function cacheDirectory(cacheRoot, fingerprint) {
  requireCondition(typeof cacheRoot === 'string' && cacheRoot.length > 0, 'CACHE_PATH_REJECTED');
  const root = path.resolve(cacheRoot);
  requireCondition(root !== path.parse(root).root && root !== SUITE_ROOT
    && root !== path.resolve(SUITE_ROOT, '../..'), 'CACHE_PATH_REJECTED');
  noLinks(root);
  const directory = path.join(root, fingerprint);
  requireCondition(path.dirname(directory) === root, 'CACHE_PATH_REJECTED');
  noLinks(directory);
  return { root, directory };
}

function openRegular(file) {
  noLinks(file);
  let descriptor;
  try {
    descriptor = fs.openSync(file, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
    requireCondition(fs.fstatSync(descriptor).isFile(), 'CACHE_PATH_REJECTED');
    return descriptor;
  } catch (error) {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    if (error.code === 'ENOENT') throw new FrozenBuildError('CACHE_INCOMPLETE');
    throw error;
  }
}

function fileHash(file) {
  const descriptor = openRegular(file); const hash = crypto.createHash('sha256');
  const buffer = Buffer.alloc(1024 * 1024); let bytes = 0;
  try {
    for (let read = fs.readSync(descriptor, buffer); read; read = fs.readSync(descriptor, buffer)) {
      bytes += read; hash.update(buffer.subarray(0, read));
    }
  } finally { fs.closeSync(descriptor); }
  return { sha256: hash.digest('hex'), bytes };
}

function readJson(file, maxBytes = 1024 * 1024) {
  const descriptor = openRegular(file);
  try {
    const size = fs.fstatSync(descriptor).size;
    requireCondition(size > 0 && size <= maxBytes, 'MANIFEST_INVALID');
    const body = Buffer.alloc(size);
    requireCondition(fs.readSync(descriptor, body, 0, size, 0) === size, 'MANIFEST_INVALID');
    return JSON.parse(body.toString('utf8'));
  } finally { fs.closeSync(descriptor); }
}

function tarInteger(header, start, length) {
  const text = header.subarray(start, start + length).toString('ascii').replace(/\0/g, '').trim();
  requireCondition(/^[0-7]+$/.test(text), 'ARCHIVE_FORMAT_REJECTED');
  const number = Number.parseInt(text, 8);
  requireCondition(Number.isSafeInteger(number) && number >= 0, 'ARCHIVE_FORMAT_REJECTED');
  return number;
}

function anonymousArchive(file, imageIds) {
  const descriptor = openRegular(file); const entries = new Map();
  try {
    const total = fs.fstatSync(descriptor).size; let offset = 0; let ended = false;
    for (let count = 0; offset < total && count < 20000; count += 1) {
      const header = Buffer.alloc(512);
      requireCondition(fs.readSync(descriptor, header, 0, 512, offset) === 512, 'ARCHIVE_FORMAT_REJECTED');
      if (header.every((byte) => byte === 0)) {
        // 空结束块后不得夹带第二段归档，避免Docker与本工具解析出不同tag。
        requireCondition(total - offset >= 1024, 'ARCHIVE_FORMAT_REJECTED');
        const remainder = Buffer.alloc(65536);
        while (offset < total) {
          const read = fs.readSync(descriptor, remainder, 0, Math.min(remainder.length, total - offset), offset);
          requireCondition(read > 0 && remainder.subarray(0, read).every((byte) => byte === 0), 'ARCHIVE_FORMAT_REJECTED');
          offset += read;
        }
        ended = true; break;
      }
      const checksum = tarInteger(header, 148, 8);
      const sum = [...header].reduce((value, byte, index) => value + (index >= 148 && index < 156 ? 32 : byte), 0);
      requireCondition(checksum === sum, 'ARCHIVE_FORMAT_REJECTED');
      const stringAt = (start, size) => header.subarray(start, start + size).toString('utf8').split('\0')[0];
      const prefix = stringAt(345, 155); const name = `${prefix ? `${prefix}/` : ''}${stringAt(0, 100)}`;
      requireCondition(/^[a-z0-9_./-]+$/i.test(name) && !name.startsWith('/')
        && !name.split('/').some((part) => part === '..' || part === '.'), 'ARCHIVE_FORMAT_REJECTED');
      const size = tarInteger(header, 124, 12); const type = header[156];
      requireCondition([0, 48, 53].includes(type) && (type !== 53 || size === 0)
        && !entries.has(name), 'ARCHIVE_FORMAT_REJECTED');
      entries.set(name, { offset: offset + 512, size, regular: type !== 53 });
      offset += 512 + Math.ceil(size / 512) * 512;
      requireCondition(offset <= total, 'ARCHIVE_FORMAT_REJECTED');
    }
    requireCondition(ended && entries.has('manifest.json'), 'ARCHIVE_FORMAT_REJECTED');
    const readEntry = (name, maxBytes = 8 * 1024 * 1024) => {
      const entry = entries.get(name);
      requireCondition(entry?.regular && entry.size <= maxBytes, 'ARCHIVE_FORMAT_REJECTED');
      const data = Buffer.alloc(entry.size);
      requireCondition(fs.readSync(descriptor, data, 0, data.length, entry.offset) === data.length, 'ARCHIVE_FORMAT_REJECTED');
      return data;
    };
    const manifest = JSON.parse(readEntry('manifest.json', 1024 * 1024));
    const expected = new Set(imageIds); const observed = new Set();
    // Docker 29/containerd的.Id是OCI index摘要，经典存储的.Id则是config摘要。
    // 沿归档内不可变descriptor验证到config，不能把两者直接等同或放宽为任意config。
    const allowedConfigs = new Map();
    if (entries.has('index.json')) {
      const index = JSON.parse(readEntry('index.json', 1024 * 1024));
      const roots = index.manifests ?? [];
      requireCondition(Array.isArray(roots) && roots.length === expected.size
        && roots.every((item) => expected.has(item.digest)), 'ARCHIVE_ID_MISMATCH');
      const visit = (descriptor, root, depth = 0) => {
        requireCondition(depth <= 8 && IMAGE_ID.test(descriptor.digest ?? ''), 'ARCHIVE_FORMAT_REJECTED');
        const body = readEntry(`blobs/sha256/${descriptor.digest.slice(7)}`);
        requireCondition(`sha256:${digest(body)}` === descriptor.digest && body.length === descriptor.size, 'ARCHIVE_ID_MISMATCH');
        const value = JSON.parse(body);
        if (value.manifests) for (const child of value.manifests) visit(child, root, depth + 1);
        else {
          requireCondition(IMAGE_ID.test(value.config?.digest ?? ''), 'ARCHIVE_FORMAT_REJECTED');
          const config = readEntry(`blobs/sha256/${value.config.digest.slice(7)}`);
          requireCondition(`sha256:${digest(config)}` === value.config.digest, 'ARCHIVE_ID_MISMATCH');
          allowedConfigs.set(value.config.digest, new Set([...(allowedConfigs.get(value.config.digest) ?? []), root]));
        }
      };
      for (const root of roots) visit(root, root.digest);
    }
    requireCondition(Array.isArray(manifest) && manifest.length > 0, 'ARCHIVE_ID_MISMATCH');
    for (const item of manifest) {
      requireCondition(object(item) && (item.RepoTags == null || (Array.isArray(item.RepoTags) && item.RepoTags.length === 0)), 'ARCHIVE_TAGS_REJECTED');
      requireCondition(typeof item.Config === 'string' && Array.isArray(item.Layers)
        && item.Layers.every((name) => entries.get(name)?.regular), 'ARCHIVE_FORMAT_REJECTED');
      const id = `sha256:${digest(readEntry(item.Config))}`;
      if (allowedConfigs.size) {
        requireCondition(allowedConfigs.has(id), 'ARCHIVE_ID_MISMATCH');
        for (const root of allowedConfigs.get(id)) observed.add(root);
      } else {
        requireCondition(expected.has(id) && !observed.has(id), 'ARCHIVE_ID_MISMATCH'); observed.add(id);
      }
    }
    requireCondition(observed.size === expected.size, 'ARCHIVE_ID_MISMATCH');
    if (entries.has('repositories')) {
      const repositories = JSON.parse(readEntry('repositories', 1024 * 1024));
      requireCondition(object(repositories) && Object.keys(repositories).length === 0, 'ARCHIVE_TAGS_REJECTED');
    }
    if (entries.has('index.json')) {
      const inspectAnnotations = (value) => {
        if (!object(value) && !Array.isArray(value)) return;
        for (const [key, child] of Object.entries(value)) {
          if (key === 'org.opencontainers.image.ref.name' || key === 'io.containerd.image.name') {
            requireCondition(expected.has(child) || expected.has(`sha256:${child}`), 'ARCHIVE_TAGS_REJECTED');
          }
          inspectAnnotations(child);
        }
      };
      inspectAnnotations(JSON.parse(readEntry('index.json', 1024 * 1024)));
    }
  } finally { fs.closeSync(descriptor); }
}

function identityFrom(manifest) {
  return { schema_version: 1, tool_version: VERSION, source_digest: manifest.source_digest,
    node_version: manifest.node_version, dependencies: manifest.dependencies,
    source_files: manifest.source_files, images: manifest.images.map(({ name, id }) => ({ name, id })) };
}

function validateManifest(manifest, fingerprint, source) {
  requireCondition(keysExactly(manifest, ['schema_version', 'tool_version', 'fingerprint', 'source_digest',
    'node_version', 'dependencies', 'source_files', 'images', 'archive'])
    && manifest.schema_version === 1 && manifest.tool_version === VERSION
    && manifest.fingerprint === fingerprint, 'MANIFEST_INVALID');
  requireCondition(manifest.source_digest === source, 'SOURCE_MISMATCH');
  requireCondition(manifest.node_version === process.versions.node, 'TOOL_VERSION_MISMATCH');
  requireCondition(stable(normalizeDependencies(manifest.dependencies)) === stable(manifest.dependencies), 'MANIFEST_INVALID');
  requireCondition(Array.isArray(manifest.source_files) && manifest.source_files.every((item) =>
    keysExactly(item, ['path', 'sha256']) && LOCK_FILES.has(item.path) && DIGEST.test(item.sha256)), 'MANIFEST_INVALID');
  requireCondition(Array.isArray(manifest.images) && manifest.images.length === 3, 'MANIFEST_INVALID');
  manifest.images.forEach((item, index) => {
    requireCondition(keysExactly(item, ['name', 'id', 'repo_digests', 'suite', 'source'])
      && item.name === NAMES[index] && IMAGE_ID.test(item.id) && item.suite === 'workspace-test'
      && item.source === source && Array.isArray(item.repo_digests)
      && item.repo_digests.every((value) => typeof value === 'string' && /^[a-z0-9._:/-]+@sha256:[a-f0-9]{64}$/.test(value)), 'MANIFEST_INVALID');
  });
  requireCondition(keysExactly(manifest.archive, ['file', 'sha256', 'bytes'])
    && manifest.archive.file === 'images.tar' && DIGEST.test(manifest.archive.sha256)
    && Number.isSafeInteger(manifest.archive.bytes) && manifest.archive.bytes > 0, 'MANIFEST_INVALID');
  requireCondition(digest(stable(identityFrom(manifest))) === fingerprint, 'FINGERPRINT_MISMATCH');
  return manifest;
}

function readFrozen(directory, fingerprint, source) {
  const manifest = validateManifest(readJson(path.join(directory, 'manifest.json')), fingerprint, source);
  const file = path.join(directory, 'images.tar'); const actual = fileHash(file);
  requireCondition(actual.sha256 === manifest.archive.sha256 && actual.bytes === manifest.archive.bytes, 'ARCHIVE_MISMATCH');
  anonymousArchive(file, manifest.images.map(({ id }) => id));
  return manifest;
}

async function inspectImage(docker, reference, expectedId, source) {
  const raw = JSON.parse(await docker(['image', 'inspect', '--format', INSPECT, reference], COMMAND_OPTIONS));
  requireCondition(raw?.id === expectedId, 'IMAGE_ID_MISMATCH');
  requireCondition(raw.suite === 'workspace-test' && raw.source === source, 'IMAGE_SOURCE_MISMATCH');
  const repoDigests = raw.repo_digests ?? [];
  requireCondition(Array.isArray(repoDigests) && repoDigests.every((value) => typeof value === 'string'
    && /^[a-z0-9._:/-]+@sha256:[a-f0-9]{64}$/.test(value)), 'IMAGE_METADATA_INVALID');
  return { id: raw.id, repo_digests: [...new Set(repoDigests)].sort(), suite: raw.suite, source: raw.source };
}

export async function saveFrozenBuild(session, { docker = defaultDocker, cacheRoot = CACHE_ROOT } = {}) {
  let created = null;
  try {
    const source = sourceDigest(session); const images = sessionImages(session, true);
    const dependencies = normalizeDependencies(session.dependencies);
    const identity = identityFrom({ source_digest: source, node_version: process.versions.node,
      dependencies, source_files: sourceFiles(session), images });
    const fingerprint = digest(stable(identity)); const { root, directory } = cacheDirectory(cacheRoot, fingerprint);
    const metadata = [];
    for (const image of images) metadata.push({ name: image.name, ...await inspectImage(docker, image.tag, image.id, source) });
    if (fs.existsSync(directory)) {
      const manifest = readFrozen(directory, fingerprint, source);
      requireCondition(stable(identityFrom(manifest)) === stable(identity), 'FINGERPRINT_MISMATCH');
      return { fingerprint, manifest };
    }
    fs.mkdirSync(root, { recursive: true }); noLinks(root);
    fs.mkdirSync(directory, { mode: 0o700 }); created = directory;
    const temporary = path.join(directory, `.images-${crypto.randomUUID()}.tar`);
    await docker(['image', 'save', '--output', temporary, ...new Set(images.map(({ id }) => id))], TRANSFER_OPTIONS);
    const archive = fileHash(temporary);
    requireCondition(archive.bytes > 0, 'ARCHIVE_FORMAT_REJECTED');
    anonymousArchive(temporary, images.map(({ id }) => id));
    fs.renameSync(temporary, path.join(directory, 'images.tar'));
    const manifest = { ...identity, fingerprint, images: metadata, archive: { file: 'images.tar', ...archive } };
    const pendingManifest = path.join(directory, `.manifest-${crypto.randomUUID()}.tmp`);
    fs.writeFileSync(pendingManifest, JSON.stringify(manifest, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    fs.renameSync(pendingManifest, path.join(directory, 'manifest.json'));
    created = null;
    return { fingerprint, manifest };
  } catch (error) {
    if (created) { noLinks(created); fs.rmSync(created, { recursive: true, force: true }); }
    if (error instanceof FrozenBuildError) throw error;
    throw new FrozenBuildError('FROZEN_SAVE_FAILED');
  }
}

export async function loadFrozenBuild(session, fingerprint, { docker = defaultDocker, cacheRoot = CACHE_ROOT } = {}) {
  try {
    requireCondition(typeof fingerprint === 'string' && DIGEST.test(fingerprint), 'FINGERPRINT_INVALID');
    const source = sourceDigest(session); const images = sessionImages(session, false);
    const { directory } = cacheDirectory(cacheRoot, fingerprint);
    const manifest = readFrozen(directory, fingerprint, source);
    images.forEach((image, index) => requireCondition(!image.id || image.id === manifest.images[index].id, 'IMAGE_ID_MISMATCH'));
    if (session.dependencies !== undefined) requireCondition(stable(normalizeDependencies(session.dependencies)) === stable(manifest.dependencies), 'DEPENDENCY_MISMATCH');
    if (session.source_before.files) requireCondition(stable(sourceFiles(session)) === stable(manifest.source_files), 'SOURCE_MISMATCH');
    for (let index = 0; index < images.length; index += 1) {
      const current = await docker(['image', 'ls', '--no-trunc', '--format', '{{.ID}}', images[index].tag], COMMAND_OPTIONS);
      requireCondition(!current || current === manifest.images[index].id, 'IMAGE_TAG_CONFLICT');
    }
    await docker(['image', 'load', '--input', path.join(directory, 'images.tar')], TRANSFER_OPTIONS);
    // 先验证全部导入ID和来源，再挂本轮tag；失败时由主入口按登记意图统一清理。
    for (const image of manifest.images) await inspectImage(docker, image.id, image.id, source);
    images.forEach((image, index) => { image.id = manifest.images[index].id; });
    for (const image of images) {
      await docker(['image', 'tag', image.id, image.tag], COMMAND_OPTIONS);
      await inspectImage(docker, image.tag, image.id, source);
    }
    session.dependencies = manifest.dependencies;
    return { fingerprint, manifest };
  } catch (error) {
    if (error instanceof FrozenBuildError) throw error;
    throw new FrozenBuildError('FROZEN_LOAD_FAILED');
  }
}
