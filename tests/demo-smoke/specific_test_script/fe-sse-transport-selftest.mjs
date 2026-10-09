import http from 'node:http'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { chromium } from 'playwright'
import { createSseRelay } from './fe-sse-transport.mjs'

// FE_009测试工具自检，不计产品分类通过：本地HTTP+正常CORS+原生EventSource真实断开/恢复。
const runId = '10000000-0000-4000-8000-000000000001'
const otherRun = '10000000-0000-4000-8000-000000000002'
const officialPath = `/api/v1/runs/${runId}/events/stream`
const frames = ['id: 1\nevent: run.created\ndata: {"seq":1}\n\n', 'id: 2\nevent: task.queued\ndata: {"seq":2}\n\n']

async function fixture() {
  const sockets = new Set()
  const server = http.createServer((request, response) => {
    if (!request.url.startsWith(officialPath)) { response.end('<!doctype html><title>FE_009正常浏览器安全策略</title>'); return }
    response.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' })
    const cursor = Number(request.headers['last-event-id'] ?? new URL(request.url, 'http://test').searchParams.get('after_seq') ?? 0)
    for (let seq = cursor + 1; seq <= 2; seq++) response.write(frames[seq - 1])
    if (cursor >= 2) response.write('id: 3\nevent: run.started\ndata: {"seq":3}\n\n')
  })
  server.on('connection', (socket) => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)) })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  const origin = `http://127.0.0.1:${server.address().port}`
  const relay = await createSseRelay({ baseUrl: origin, frontendUrl: origin, runId, lifetimeMs: 8000 })
  return { origin, relay, async close() { await relay.close(); for (const socket of sockets) socket.destroy(); await new Promise((resolve) => server.close(resolve)) } }
}

test('FE_009工具边界：越界Run/Origin/方法/游标/凭据URL均拒绝，允许正式请求与限定CORS预检', async () => {
  const f = await fixture()
  try {
    await assert.rejects(createSseRelay({ baseUrl: `${f.origin.replace('http://', 'http://safe:credential@')}`, frontendUrl: f.origin, runId }), /凭据/)
    await assert.rejects(createSseRelay({ baseUrl: f.origin, frontendUrl: f.origin, runId: '../escape' }), /UUID/)
    const headers = { Origin: f.origin }
    for (const [route, options, status] of [
      [`/api/v1/runs/${otherRun}/events/stream`, { headers }, 403],
      [officialPath, { headers: { Origin: 'http://unrelated.invalid' } }, 403],
      [officialPath, { method: 'POST', headers }, 405],
      [`${officialPath}?after_seq=-1`, { headers }, 403],
      [`${officialPath}?target=http://unrelated.invalid`, { headers }, 403],
      [officialPath, { headers: { ...headers, 'Last-Event-ID': 'invalid' } }, 403],
    ]) assert.equal((await fetch(f.relay.origin + route, options)).status, status)
    const preflight = await fetch(f.relay.origin + officialPath, { method: 'OPTIONS', headers: { ...headers, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'Last-Event-ID' } })
    assert.equal(preflight.status, 204)
    assert.equal(preflight.headers.get('access-control-allow-origin'), f.origin)
    assert.equal((await fetch(f.relay.origin + officialPath, { method: 'OPTIONS', headers: { ...headers, 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'Authorization' } })).status, 403)
    const controller = new AbortController()
    const positive = await fetch(f.relay.url(0), { headers, signal: controller.signal })
    assert.equal(positive.status, 200)
    assert.equal(positive.headers.get('access-control-allow-origin'), f.origin)
    const reader = positive.body.getReader()
    let received = ''
    while (received.length < frames.join('').length) {
      const part = await reader.read()
      assert.equal(part.done, false, '原始帧尚未交付完成就断开')
      received += new TextDecoder().decode(part.value)
    }
    assert.equal(received, frames.join(''), '透传必须保留上游全部原始帧字节')
    controller.abort()
    process.stdout.write('FE_009工具边界正负自检通过；正式路径透传字节完全一致。\n')
  } finally { await f.close() }
})

test('FE_009工具断线：302+限定Origin CORS使用原生EventSource，socket断开产生error，恢复请求携带游标', async () => {
  const f = await fixture()
  let browser
  try {
    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext()
    try {
      const page = await context.newPage()
      await page.route((url) => url.origin === f.origin && url.pathname === officialPath, (route) => route.fulfill({ status: 302, headers: { Location: f.relay.origin + new URL(route.request().url()).pathname + new URL(route.request().url()).search, 'Cache-Control': 'no-store' } }))
      await page.goto(f.origin)
      await page.evaluate((path) => {
        window.observed = { opens: 0, errors: 0, seq: [] }
        window.source = new EventSource(path + '?after_seq=0')
        source.addEventListener('open', () => observed.opens++)
        source.addEventListener('error', () => observed.errors++)
        for (const type of ['run.created', 'task.queued', 'run.started']) source.addEventListener(type, (event) => observed.seq.push(Number(event.lastEventId)))
      }, officialPath)
      await page.waitForFunction(() => window.observed.seq.includes(2), { timeout: 5000 })
      assert.equal(f.relay.connections.length, 1)
      assert.equal(f.relay.disconnect(), 1)
      await page.waitForFunction(() => window.observed.errors > 0, { timeout: 5000 })
      await page.waitForFunction(() => window.observed.seq.includes(3), { timeout: 7000 })
      const observed = await page.evaluate(() => window.observed)
      assert.deepEqual(observed.seq, [1, 2, 3])
      assert.equal(observed.errors, 1)
      assert.ok(f.relay.connections.some((trace) => Number(trace.last_event_id ?? trace.after_seq ?? 0) === 2))
      assert.equal(f.relay.connections[0].severed, true)
      process.stdout.write(`FE_009原生断线/恢复自检通过；seq=${observed.seq.join('/')}；error=${observed.errors}；游标=2。\n`)
      await page.evaluate(() => window.source.close())
      // 负哨兵：模仿当前生产onerror.close只用于工具区分能力，不能作为产品检查通过。
      // 真正发生error后关闭的客户端不会重连；测试器必须能观测到请求数不再增长。
      await page.evaluate((path) => {
        window.observed = { opens: 0, errors: 0, seq: [] }
        window.source = new EventSource(path + '?after_seq=0')
        source.addEventListener('open', () => observed.opens++)
        source.addEventListener('error', () => { observed.errors++; source.close() })
        source.addEventListener('task.queued', (event) => observed.seq.push(Number(event.lastEventId)))
      }, officialPath)
      await page.waitForFunction(() => window.observed.seq.includes(2), { timeout: 5000 })
      const negativeCount = f.relay.connections.length
      assert.ok(f.relay.disconnect() > 0)
      await page.waitForFunction(() => window.observed.errors > 0, { timeout: 5000 })
      await page.waitForTimeout(3500)
      assert.equal(f.relay.connections.length, negativeCount, '工具应区分error后直接关闭导致不再重连的负哨兵')
      assert.equal(await page.evaluate(() => window.source.readyState), 2)
      process.stdout.write('FE_009重连负哨兵自检通过；真实error后close保持无新增请求，不会误报恢复通过。\n')
    } finally { await context.close() }
  } finally { await browser?.close(); await f.close() }
})
