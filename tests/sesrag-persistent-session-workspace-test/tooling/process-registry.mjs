import fs from 'node:fs';
import { AsyncLocalStorage } from 'node:async_hooks';
import { StringDecoder } from 'node:string_decoder';
import crypto from 'node:crypto';
import { spawn, execFileSync } from 'node:child_process';
import { sanitizeText } from './report.mjs';

const execution = new AsyncLocalStorage();
export const withProcessContext = (options, action) => {
  const inherited = execution.getStore() ?? {};
  const deadline = Math.min(inherited.deadline ?? Infinity, options.deadline ?? Infinity);
  return execution.run({ ...inherited, ...options, ...(Number.isFinite(deadline) ? { deadline } : {}) }, action);
};
export function cleanChildEnvironment(extra = {}) {
  return { ...Object.fromEntries(Object.entries(process.env).filter(([key]) =>
    !/^(?:WS_|COMPOSE_|PG|POSTGRES|DATABASE|REDIS|SESSION_PG|MODEL|EMBEDDING|PROVIDER|OPENAI|ANTHROPIC)|(?:DSN|API_KEY|SECRET|PASSWORD|TOKEN)$/i.test(key))), ...extra };
}

// 创建时间和可执行文件用于防止恢复时误杀已复用 PID 的其它进程。
export function processIdentity(pid) {
  if (!Number.isSafeInteger(Number(pid)) || Number(pid) <= 0) return null;
  try {
    if (process.platform === 'win32') {
      const script = `$p=Get-CimInstance Win32_Process -Filter 'ProcessId=${Number(pid)}'; if($p){[pscustomobject]@{pid=$p.ProcessId;parent_pid=$p.ParentProcessId;created_at=$p.CreationDate.ToUniversalTime().ToString('o');executable=$p.ExecutablePath}|ConvertTo-Json -Compress}`;
      const value = execFileSync('pwsh', ['-NoProfile', '-Command', script], { encoding: 'utf8', windowsHide: true, timeout: 10000 }).trim();
      if (!value) return null;
      const identity = JSON.parse(value);
      if (!identity.executable) return null;
      identity.executable = crypto.createHash('sha256').update(identity.executable.toLowerCase()).digest('hex');
      return identity;
    }
    const stat = fs.readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].split(' ');
    return { pid: Number(pid), parent_pid: Number(stat[1]), process_group: Number(stat[2]), created_at: stat[19], executable: crypto.createHash('sha256').update(fs.readlinkSync(`/proc/${pid}/exe`)).digest('hex') };
  } catch { return null; }
}

export function sameProcess(expected, actual) {
  return !!expected?.created_at && !!expected?.executable && !!actual && expected.pid === actual.pid
    && expected.created_at === actual.created_at && expected.executable === actual.executable;
}

export function terminateRegistered(entry) {
  if (entry.ownership_unverified) throw new Error('子孙进程归属未核验，拒绝猜测终止');
  const actual = processIdentity(entry.pid);
  if (!actual) {
    if (entry.process_tree_unverified) throw new Error('父进程已退出但子孙身份未核验，不能宣布资源已回收');
    try { process.kill(entry.pid, 0); } catch (error) { if (error.code === 'ESRCH') return 'already_exited'; }
    throw new Error('无法核验仍可能活跃的登记进程，拒绝猜测终止');
  }
  if (!sameProcess(entry, actual)) throw new Error('进程身份不符，拒绝终止复用 PID');
  // 不按进程名终止；Windows /T 仅针对核验后的父进程树。
  if (process.platform === 'win32') execFileSync('taskkill', ['/PID', String(entry.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore', timeout: 15000 });
  else if (entry.process_group === entry.pid) process.kill(-entry.pid, 'SIGKILL');
  else process.kill(entry.pid, 'SIGKILL');
  return 'terminated';
}

function processDescendants(parent, exitedAt) {
  let entries;
  if (process.platform === 'win32') {
    const script = "@(Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath} | ForEach-Object {[pscustomobject]@{pid=$_.ProcessId;parent_pid=$_.ParentProcessId;created_at=$_.CreationDate.ToUniversalTime().ToString('o');executable=$_.ExecutablePath}})|ConvertTo-Json -Compress";
    const raw = execFileSync('pwsh', ['-NoProfile', '-Command', script], { encoding: 'utf8', windowsHide: true, timeout: 10000, stdio: ['ignore', 'pipe', 'ignore'] });
    const records = JSON.parse(raw || '[]');
    entries = (Array.isArray(records) ? records : [records]).filter((entry) => Date.parse(entry.created_at) <= exitedAt
      && Date.parse(entry.created_at) >= (Date.parse(parent.created_at) || Date.parse(parent.observed_at)) - 1000)
      .map((entry) => ({ ...entry, executable: crypto.createHash('sha256').update(entry.executable.toLowerCase()).digest('hex') }));
  } else {
    entries = fs.readdirSync('/proc').filter((name) => /^\d+$/.test(name)).map((name) => processIdentity(Number(name))).filter(Boolean);
  }
  const found = new Set([parent.pid]); let changed = true;
  while (changed) {
    changed = false;
    for (const entry of entries) if (!found.has(entry.pid) && (found.has(entry.parent_pid)
      || (process.platform !== 'win32' && parent.process_group && entry.process_group === parent.process_group && Number(entry.created_at) >= Number(parent.created_at)))) {
      found.add(entry.pid); changed = true;
    }
  }
  return entries.filter((entry) => entry.pid !== parent.pid && found.has(entry.pid)).map((entry) => ({ ...entry, is_descendant: true,
    ...(!parent.created_at ? { ownership_unverified: true } : {}) }));
}

export async function runCommand(command, args, options = {}) {
  const { timeoutMs: requestedTimeout = 30000, env = cleanChildEnvironment(), cwd, secrets = [], onProcess, logPath,
    maxBytes = 10 * 1024 * 1024, signal, rawOutput = false, deadline, identityReader = processIdentity } = { ...execution.getStore(), ...options };
  const timeoutMs = deadline ? Math.min(requestedTimeout, deadline - Date.now()) : requestedTimeout;
  if (deadline && timeoutMs <= 0) throw new Error('命令阶段总期限已到，停止后续命令');
  if (signal?.aborted) throw Object.assign(new Error('运行已中断，停止创建子进程'), { exitCode: 130 });
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || !Number.isInteger(maxBytes) || maxBytes < 128) throw new Error('命令超时或日志上限无效');
  return new Promise((resolve, reject) => {
    const observedAt = new Date().toISOString();
    const child = spawn(command, args, { cwd, env, windowsHide: true, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] });
    let output = ''; const streams = ['', '']; let truncated = false; let timedOut = false; let entry; let failure; let settled = false; let descendants = [];
    const decoders = [new StringDecoder('utf8'), new StringDecoder('utf8')];
    const capture = (text, stream) => {
      if (truncated) return;
      output += text; streams[stream] += text;
      if (Buffer.byteLength(output) > maxBytes) { output = ''; streams.fill(''); truncated = true; }
    };
    child.stdout.on('data', (data) => capture(decoders[0].write(data), 0));
    child.stderr.on('data', (data) => capture(decoders[1].write(data), 1));
    const finish = (error, value) => {
      if (settled) return; settled = true;
      clearTimeout(timer); clearTimeout(terminationTimer); signal?.removeEventListener('abort', abort);
      if (error) reject(error); else resolve(value);
    };
    let terminationTimer;
    const stop = () => {
      for (const candidate of [...descendants].reverse().concat(entry ? [entry] : [])) {
        try { terminateRegistered(candidate); if (!candidate.process_tree_unverified) onProcess?.(candidate, false); }
        catch (error) { failure ??= error; }
      }
      if (!terminationTimer) terminationTimer = setTimeout(() => {
        child.stdout.destroy(); child.stderr.destroy(); child.unref();
        finish(failure ?? new Error('子进程未在终止期限内退出'));
      }, 5000);
    };
    const abort = () => { failure = Object.assign(new Error('运行已中断'), { exitCode: 130 }); stop(); };
    const timer = setTimeout(() => { timedOut = true; stop(); }, timeoutMs);
    signal?.addEventListener('abort', abort, { once: true });
    child.once('spawn', () => {
      entry = identityReader(child.pid) ?? { pid: child.pid, parent_pid: process.pid, created_at: null, executable: null, observed_at: observedAt, unverified: true };
      if (entry && process.platform !== 'win32') entry.process_group = child.pid;
      try { if (entry) onProcess?.(entry, true); }
      catch (error) { failure = error; stop(); }
      if (signal?.aborted) abort();
    });
    child.on('exit', () => {
      if (!entry) return;
      try {
        descendants = processDescendants(entry, Date.now());
        if (descendants.some((item) => item.ownership_unverified)) { entry.process_tree_unverified = true; onProcess?.(entry, true); }
        for (const descendant of descendants) onProcess?.(descendant, true);
        if (descendants.length) { failure ??= new Error('父进程先退出，仍有已登记子孙进程未结束'); stop(); }
      } catch (error) {
        entry.process_tree_unverified = true;
        try { onProcess?.(entry, true); } catch { /* 原始登记失败仍保留未知残留状态。 */ }
        failure ??= new Error(`子孙进程核验失败：${error.message}`); stop();
      }
    });
    child.on('error', (error) => finish(error));
    child.on('close', (code, signal) => {
      decoders.forEach((decoder, stream) => capture(decoder.end(), stream));
      try {
        if (entry && !entry.process_tree_unverified) onProcess?.(entry, false);
        // 超限时整段舍弃，避免截断后发布半段秘密；分块先解码，输出前再脱敏。
        const clean = (truncated ? '[日志已截断]\n' : '') + sanitizeText(output, secrets);
        if (logPath) fs.appendFileSync(logPath, clean + '\n', 'utf8');
        finish(failure, { code: code ?? 2, signal, timedOut, output: rawOutput && !truncated ? output : clean,
          stdout: rawOutput && !truncated ? streams[0] : sanitizeText(streams[0], secrets),
          stderr: rawOutput && !truncated ? streams[1] : sanitizeText(streams[1], secrets), truncated });
      } catch (error) { finish(error); }
    });
  });
}
