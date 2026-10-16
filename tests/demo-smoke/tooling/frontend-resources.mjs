import fs from 'node:fs'
import path from 'node:path'
import { randomUUID } from 'node:crypto'
import { spawn } from 'node:child_process'
import { chromium } from 'playwright'
import { assert, poll, repoRoot } from '../lib/category-kit.mjs'
import { processIdentity, stopOwnedProcess } from '../lib/process-identity.mjs'

const ownerIdentity = processIdentity(process.pid)

// LIFE_006 / FE：先登记所有权，创建后补实际PID/端口，观察关闭后才记closed。
export function frontendResource(ctx, kind, details = {}) {
  const id = randomUUID()
  const file = path.join(ctx.args.RuntimeDir, 'frontend-resources.json')
  const update = (status, extra = {}) => {
    // QLT父进程与FE子进程共享登记；排他创建锁文件保护整个读改写，不能共用.tmp并发覆盖。
    const lock = file + '.lock', until = Date.now() + 5000
    let descriptor
    while (descriptor === undefined) {
      try { descriptor = fs.openSync(lock, 'wx') }
      catch (error) {
        // Windows另一个进程删除中的锁可能短暂报告EPERM；同样只重试到固定截止。
        if (!['EEXIST','EPERM'].includes(error.code) || Date.now() >= until) throw error
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10)
      }
    }
    try {
    const data = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {
      schema_version: 1, parent_run_id: ctx.args.RunId, project: ctx.context.compose_project, resources: [],
    }
    assert.equal(data.parent_run_id, ctx.args.RunId)
    assert.equal(data.project, ctx.context.compose_project)
    const row = data.resources.find(item => item.id === id)
    const value = { status, ...extra, updated_at: new Date().toISOString() }
    if (status === 'running' && extra.pid) value.process_identity = extra.process_identity ?? processIdentity(extra.pid)
    if (row) Object.assign(row, value)
    else data.resources.push({ id, kind, owner_pid: process.pid, owner_identity: ownerIdentity, ...details, ...value })
    fs.writeFileSync(file + '.tmp', JSON.stringify(data, null, 2))
    // 与取锁共享同一5秒截止；Windows读句柄瞬态占用不能破坏旧事实或丢弃pending内容。
    while (true) {
      try { fs.renameSync(file + '.tmp', file); break }
      catch (error) {
        if (!['EPERM','EACCES','EBUSY'].includes(error.code) || Date.now() >= until) throw error
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10)
      }
    }
    } finally { fs.closeSync(descriptor); fs.unlinkSync(lock) }
  }
  update('planned')
  return { id, running: details => update('running', details), closed: details => update('closed', details) }
}

export async function registeredFrontendProcess(ctx, command, args, { timeoutMs = 60000, kind = 'frontend-child', env = {} } = {}) {
  const row = frontendResource(ctx, kind)
  const child = spawn(command, args, { cwd: repoRoot, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, ...env } })
  let stdout = '', stderr = '', timedOut = false, identity, bodyError, observedClose = false
  child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8')
  child.stdout.on('data', value => { stdout += value })
  child.stderr.on('data', value => { stderr += value })
  let rejectOperation
  const closed = new Promise(resolve => child.once('close', code => { observedClose = true; resolve(code ?? -1) }))
  // EventEmitter同步异常必须转换为可await失败；close监听在spawn/error之前安装。
  const operation = new Promise((resolve, reject) => {
    rejectOperation = reject
    child.once('error', reject)
    child.once('spawn', () => {
      try {
        identity = processIdentity(child.pid)
        if (identity) row.running({ pid: child.pid, process_identity: identity })
        // 已快速退出且查不到身份时只等待真实close，绝不登记虚构出生信息。
      } catch (error) { reject(error) }
    })
    closed.then(resolve)
  })
  const terminate = () => {
    if (observedClose) return
    if (identity) stopOwnedProcess(identity)
    else if (child.pid && child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
  }
  const timer = setTimeout(() => {
    timedOut = true
    // 终止和登记故障均由同一个await/finally收束，不能从计时器回调逃逸。
    rejectOperation(Object.assign(new Error('辅助进程树超时'), { code: 'PROCESS_TIMEOUT' }))
  }, timeoutMs)
  let code
  try {
    code = await operation
  } catch (error) { bodyError = error } finally {
    clearTimeout(timer)
    const errors = []
    try { terminate() } catch (error) { errors.push(error) }
    let deadline
    try {
      code = await Promise.race([closed, new Promise((_, reject) => { deadline = setTimeout(() => reject(new Error('子进程/管道关闭超过5秒')), 5000) })])
    } catch (error) { errors.push(error) } finally { clearTimeout(deadline) }
    if (observedClose) {
      try { row.closed({ pid: child.pid, process_identity: identity, observed_process_closed: true, process_exit_code: code, process_signal: child.signalCode, timed_out: timedOut, launch_error: bodyError?.code }) }
      catch (error) { errors.push(error) }
    }
    if (errors.length) throw new AggregateError([bodyError,...errors].filter(Boolean),[bodyError?.message,...errors.map(error=>error.message)].filter(Boolean).join('; '))
  }
  if (bodyError && !timedOut) throw bodyError
  return { code: timedOut ? 124 : code, stdout, stderr, timed_out: timedOut }
}

export async function registeredBrowser(ctx) {
  const resource = frontendResource(ctx, 'browser')
  let server, browser
  try {
    server = await chromium.launchServer({ headless: true })
    const pid = server.process().pid
    resource.running({ pid })
    browser = await chromium.connect(server.wsEndpoint())
    return {
      browser,
      async withPage(fn) {
        const contextRow = frontendResource(ctx, 'context', { browser_resource: resource.id })
        let context, page, pageRow, closed = false
        const streams = []
        try {
          context = await browser.newContext()
          context.on('close', () => { closed = true })
          contextRow.running()
          // 页请求在创建前已安装路由，包含导航/重连产生的每条SSE。
          await context.route('**/events/stream?*', async route => {
            const row = frontendResource(ctx, 'sse', { context_resource: contextRow.id, url: route.request().url() })
            row.running(); streams.push(row)
            await route.fallback()
          })
          pageRow = frontendResource(ctx, 'page', { context_resource: contextRow.id })
          page = await context.newPage()
          pageRow.running()
          page.setDefaultTimeout(10000)
          // 每条真实EventSource网络请求在放行前登记；字节与回调仍由浏览器原生实现处理。
          return await fn(page, context)
        } finally {
          if (context) await context.close()
          if (page) { assert.ok(page.isClosed()); pageRow.closed({ observed_page_closed: true }) }
          else pageRow?.closed({ creation_failed: true })
          assert.ok(!context || closed)
          contextRow.closed({ observed_context_closed: closed, creation_failed: !context })
          for (const row of streams) row.closed({ observed_page_closed: page.isClosed(), transport_owner_closed: true })
        }
      },
      async close() {
        const errors = []
        try { await browser.close() } catch (error) { errors.push(error) }
        // 客户端关闭异常也必须尝试真实服务器关闭，观察退出后才登记closed。
        try { await server.close() } catch (error) { errors.push(error) }
        try {
          await poll(async () => server.process().exitCode !== null || server.process().signalCode !== null, 5000)
          assert.equal(browser.isConnected(), false)
          resource.closed({ pid, observed_browser_disconnected: true, process_exit_code: server.process().exitCode, process_signal: server.process().signalCode })
        } catch (error) { errors.push(error) }
        if (errors.length) throw new AggregateError(errors, errors.map(error => error.message).join('; '))
      },
    }
  } catch (error) {
    const errors = [error]
    try { await browser?.close() } catch (closeError) { errors.push(closeError) }
    try { await server?.close() } catch (closeError) { errors.push(closeError) }
    if (!server || server.process().exitCode !== null || server.process().signalCode !== null) resource.closed({ creation_failed: true })
    throw new AggregateError(errors, errors.map(item => item.message).join('; '))
  }
}
