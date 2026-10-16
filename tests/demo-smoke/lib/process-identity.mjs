import fs from 'node:fs'
import { spawnSync } from 'node:child_process'
import assert from 'node:assert/strict'

// 数字PID可复用；出生时间与可执行文件共同确认身份，不记录命令行或凭据。
export function processIdentity(pid) {
  assert.ok(Number.isSafeInteger(pid) && pid > 0)
  if (process.platform === 'win32') {
    const source = `$p=Get-Process -Id ${pid} -ErrorAction SilentlyContinue; if($p){[ordered]@{pid=$p.Id;started=$p.StartTime.ToUniversalTime().Ticks.ToString();executable=$p.Path}|ConvertTo-Json -Compress}; exit 0`
    const result = spawnSync('pwsh', ['-NoProfile', '-Command', source], { encoding: 'utf8', windowsHide: true, timeout: 10000 })
    assert.equal(result.status, 0, '进程身份查询失败')
    return result.stdout.trim() ? JSON.parse(result.stdout) : null
  }
  try {
    const stat = fs.readFileSync(`/proc/${pid}/stat`, 'utf8')
    return { pid, started: stat.slice(stat.lastIndexOf(')') + 2).split(' ')[19], executable: fs.readlinkSync(`/proc/${pid}/exe`) }
  } catch (error) { if (error.code === 'ENOENT') return null; throw error }
}

export function sameProcess(saved, current) {
  return !!saved && !!current && saved.pid === current.pid && saved.started === current.started && saved.executable === current.executable
}

export function stopOwnedProcess(saved) {
  assert.ok(saved?.started && saved?.executable, '缺少出生身份，拒绝盲杀PID')
  const current = processIdentity(saved.pid)
  if (!current) return { pid: saved.pid, absent: true }
  assert.ok(sameProcess(saved, current), 'PID已复用，拒绝终止不同进程')
  assert.notEqual(saved.pid, process.pid, '恢复器不可终止自身')
  const result = process.platform === 'win32'
    ? spawnSync('taskkill', ['/PID', String(saved.pid), '/T', '/F'], { encoding: 'utf8', windowsHide: true, timeout: 15000 })
    : spawnSync('kill', ['-KILL', String(saved.pid)], { encoding: 'utf8', timeout: 15000 })
  const after = processIdentity(saved.pid)
  assert.ok(!sameProcess(saved, after), '登记进程仍存活')
  return { pid: saved.pid, terminated: true, exit_code: result.status }
}
