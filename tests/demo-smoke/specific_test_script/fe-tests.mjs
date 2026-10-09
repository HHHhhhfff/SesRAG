import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { chromium } from 'playwright'
import { JSDOM } from 'jsdom'
import { marked } from '../../../frontend/node_modules/marked/lib/marked.esm.js'
import { runCategory, assert, poll, redact } from '../lib/category-kit.mjs'
import { componentChecks, componentTitle } from './fe-component-checks.mjs'
import { createSseRelay } from './fe-sse-transport.mjs'

export const coveredCases = ['FE_001', 'FE_002', 'FE_003', 'FE_004', 'FE_005', 'FE_006', 'FE_007', 'FE_008', 'FE_009', 'FE_010', 'FE_011', 'FE_012', 'FE_013', 'FE_014', 'FE_015']
const smokeRoot = fileURLToPath(new URL('../', import.meta.url))

// FE全部用例：正式业务经六参数隔离环境；FE_009受控本地SSE透传只允许本例Run和Origin，不禁用CORS。
await runCategory('fe', async (s) => {
  const ctx = s.ctx
  const invocation = randomUUID().slice(0, 8)
  let browser
  let browserProblem
  try { browser = await chromium.launch({ headless: true }) } catch { browserProblem = '浏览器工具未安装或启动失败；请核对项目Chromium缓存' }
  const withPage = async (fn) => {
    assert.ok(browser, `Chromium无法启动：${browserProblem}`)
    const context = await browser.newContext()
    try {
      const page = await context.newPage()
      page.setDefaultTimeout(7000)
      return await fn(page, context)
    } finally { await context.close() }
  }
  const unique = (id, part) => `${id}-${part}-${ctx.args.RunId}-${invocation}`
  const renderedText = (content) => JSDOM.fragment(marked.parse(content)).textContent.trim()
  const hash = (text) => createHash('sha256').update(text).digest('hex')
  const blockedPrecondition = (reason) => Object.assign(new Error(`FE_009前置受阻：${reason}`), { blocked: true })
  const withPausedWorker = async (fn) => {
    // FE_009：停止本次Worker形成真实queued屏障；正常/失败路径都恢复，不修改数据库事实。
    try {
      const stopped = ctx.compose(['stop', 'worker'], 45000)
      if (stopped.code !== 0) throw blockedPrecondition('本次Worker暂停失败，活动queued断网条件未满足')
      return await fn()
    } finally {
      const started = ctx.compose(['start', 'worker'], 30000)
      assert.equal(started.code, 0, 'FE_009结束后本次Worker恢复失败')
      await ctx.ready(20000)
    }
  }
  const instrumentNativeStream = async (page) => {
    // FE_009：包装真正的浏览器EventSource，仅记录open/error/close，不合成事件或改变URL/重试行为。
    await page.addInitScript(() => {
      const NativeEventSource = window.EventSource
      window.__feNativeStreams = []
      window.EventSource = class extends NativeEventSource {
        constructor(url, options) {
          super(url, options)
          this.__feEntry = { url: String(url), opened: 0, errors: 0, closed: false, last_seq: 0 }
          window.__feNativeStreams.push(this.__feEntry)
          this.addEventListener('open', () => { this.__feEntry.opened++ })
          this.addEventListener('error', () => { this.__feEntry.errors++ })
          for (const type of ['run.created', 'task.queued', 'run.started', 'answer.delta', 'run.succeeded', 'run.failed', 'run.cancelled']) this.addEventListener(type, (event) => {
            this.__feEntry.last_seq = Math.max(this.__feEntry.last_seq, Number(event.lastEventId || 0))
          })
        }
        close() { if (this.__feEntry) this.__feEntry.closed = true; super.close() }
      }
    })
  }
  const withRunRelay = async (page, item, fn) => {
    let relay
    const relays = new Set()
    const submissionPath = `/api/v1/threads/${item.thread_id}/messages`
    const streamRoute = async (route) => {
      const input = new URL(route.request().url())
      if (!relay || input.origin !== new URL(ctx.args.FrontendUrl).origin || input.pathname !== relay.officialPath || route.request().method() !== 'GET') { await route.continue(); return }
      // FE_009：生产client仍发正式URL，仅以HTTP302进入本例限定CORS透传；重连同样经过本边界。
      await route.fulfill({ status: 302, headers: { Location: relay.origin + input.pathname + input.search, 'Cache-Control': 'no-store' } })
    }
    const submissionRoute = async (route) => {
      if (route.request().method() !== 'POST') { await route.continue(); return }
      const response = await route.fetch()
      if ([200, 201].includes(response.status())) {
        const body = await response.json()
        // 先启动透传再交付真实POST响应，避免Workspace立即打开SSE抢在helper建立前。
        relay = await createSseRelay({ baseUrl: ctx.args.BaseUrl, frontendUrl: ctx.args.FrontendUrl, runId: body.run_id, lifetimeMs: 60000 })
        relays.add(relay)
      }
      await route.fulfill({ response })
    }
    const streamPredicate = (url) => /\/api\/v1\/runs\/[^/]+\/events\/stream$/.test(url.pathname)
    const submissionPredicate = (url) => url.pathname === submissionPath
    await page.route(streamPredicate, streamRoute)
    await page.route(submissionPredicate, submissionRoute)
    try { return await fn(() => relay) } finally {
      try {
        await page.unroute(submissionPredicate, submissionRoute)
        await page.unroute(streamPredicate, streamRoute)
      } finally {
        // 即使页面已经关闭或解除route失败，全部实际relay仍须回收。
        const closed = await Promise.allSettled([...relays].map((item) => item.close()))
        const failed = closed.find((item) => item.status === 'rejected')
        if (failed) throw failed.reason
      }
    }
  }
  const delayFirstHistoryDelivery = async (page) => {
    const control = { used: false, run_id: null, upstream_status: null, upstream_events: [], delivered_events: [], error: null }
    // FE_009受控传输子项：仅第一次observe HTTP历史交付为空，记录真实响应安全摘要。
    // 正式API没有返回空；后续HTTP全部透传；EventSource及SSE帧来自真实API/PG。
    await page.route((url) => /\/api\/v1\/runs\/[^/]+\/events$/.test(url.pathname) && url.searchParams.get('after_seq') === '0', async (route) => {
      if (control.used || route.request().method() !== 'GET') { await route.continue(); return }
      control.used = true
      control.run_id = new URL(route.request().url()).pathname.split('/').at(-2)
      try {
        const real = await route.fetch()
        control.upstream_status = real.status()
        const payload = await real.json()
        control.upstream_events = (payload.events ?? []).map((event) => ({ seq: event.seq, type: event.type, run_id: event.run_id }))
        if (real.status() === 200 && Array.isArray(payload.events)) await route.fulfill({ response: real, json: { ...payload, events: [] } })
        else await route.fulfill({ response: real })
      } catch {
        control.error = '首次真实HTTP历史响应未获取成功，传输前置未成立'
        await route.abort().catch(() => {})
      }
    })
    return control
  }
  const activeStreamReady = async (page, runId, control, sub) => {
    try {
      await poll(async () => page.evaluate((id) => window.__feNativeStreams.some((stream) => stream.url.includes(`/runs/${id}/`) && stream.opened > 0 && !stream.closed && stream.last_seq > 0), runId), 7000, '原生SSE未收到真实首帧/open；不能判断重连行为')
      const sequences = (await page.locator('.event-seq').allTextContents()).map((text) => Number(text.trim()))
      if (!control.used || control.upstream_status !== 200 || control.error || control.run_id !== runId || !control.upstream_events.length) throw new Error('首次HTTP历史传输控制或真实历史前置未成立')
      if (!sequences.length || !sequences.every((seq) => seq > 0)) throw new Error('页面未处理初始持久历史事件，缺少可恢复游标')
      if ((await ctx.run(runId)).status !== 'queued') throw new Error('断网前不是活跃queued Run，不能使用terminal流')
      return Math.max(...sequences)
    } catch (error) {
      const native = await page.evaluate((id) => window.__feNativeStreams.filter((stream) => stream.url.includes(`/runs/${id}/`)), runId).catch(() => [])
      const evidence = ctx.evidence(`fe/FE_009-${sub}-native-precondition.json`, { transport_control: control, native_streams: native, reason: error.message })
      throw blockedPrecondition(`${error.message}；前置证据：${evidence}`)
    } finally {
      control.evidence_path = ctx.evidence(`fe/FE_009-${sub}-history-delivery.json`, { scope: '首次HTTP历史交付为空的受控传输子项，SSE仍真实PG；正式API真实响应安全摘要如下', transport_control: control })
    }
  }
  const disconnectNativeStream = async (page, relay, runId, sub) => {
    if (!relay || !relay.connections.some((connection) => connection.forwarded_bytes > 0 && !connection.closed)) throw blockedPrecondition('本例真实PG透传连接未建立，不能进行受控socket断开')
    const severed = relay.disconnect()
    try {
      await poll(async () => page.evaluate((id) => window.__feNativeStreams.some((stream) => stream.url.includes(`/runs/${id}/`) && stream.errors > 0), runId), 5000, '受控透传socket已销毁但未观察到原生SSE error，断线前提未成立')
    } catch (error) {
      const evidence = ctx.evidence(`fe/FE_009-${sub}-socket-precondition.json`, { transport_connections: relay.connections, severed_socket_count: severed, reason: error.message })
      throw blockedPrecondition(`${error.message}；证据：${evidence}`)
    }
    return { severed_socket_count: severed, native_streams: await page.evaluate((id) => window.__feNativeStreams.filter((stream) => stream.url.includes(`/runs/${id}/`)), runId) }
  }
  const watchResponse = (page, predicate) => {
    const pending = page.waitForResponse(predicate)
    // 某一步UI操作先失败时，context关闭也会拒绝等待；预先处理拒绝以免中断后续独立用例。
    void pending.catch(() => {})
    return pending
  }
  const openThread = async (page, item) => {
    await page.goto(ctx.args.FrontendUrl, { waitUntil: 'domcontentloaded' })
    const button = page.locator('.thread-item').filter({ hasText: item.title })
    await button.waitFor()
    await button.click()
    await poll(async () => (await page.locator('.topbar h2').textContent()) === item.title, 7000, '页面未选择本用例Thread')
  }
  const send = async (page, item, question, mode = 'button') => {
    const response = watchResponse(page, (r) => new URL(r.url()).pathname === `/api/v1/threads/${item.thread_id}/messages` && r.request().method() === 'POST')
    await page.locator('textarea').fill(question)
    if (mode === 'ctrl-enter') await page.locator('textarea').press('Control+Enter')
    else await page.getByRole('button', { name: '发送', exact: true }).click()
    const result = await response
    assert.equal(result.status(), 201, '浏览器提交未创建Run')
    return result.json()
  }
  const prepareHistory = async (id, part, withDocument = true) => {
    let doc
    const safeEvidence = `安全证据：${unique(id, part)}，持久会话可以恢复历史消息与引用。`
    if (withDocument) {
      const result = await ctx.upload(`${unique(id, part)}.txt`, safeEvidence)
      assert.equal(result.status, 201)
      doc = await ctx.waitDoc(result.body.document_id)
      assert.equal(doc.status, 'indexed')
    }
    const item = await ctx.thread(unique(id, part))
    // 本用例query与安全证据同文，Mock embedding可确定召回自身文本，避免读取其他分类攻击fixture。
    const submitted = await ctx.submit(item.thread_id, withDocument ? safeEvidence : `安全测试问题 ${unique(id, part)}，请说明持久会话。`)
    const run = await ctx.waitRun(submitted.run_id)
    assert.equal(run.status, 'succeeded')
    const detail = await ctx.detail(item.thread_id)
    const assistant = detail.messages.find((message) => message.run_id === run.run_id && message.role === 'assistant')
    assert.ok(assistant, '服务器未持久化最终assistant')
    assert.equal(detail.messages.filter((message) => message.role === 'assistant').length, 1)
    if (withDocument) assert.ok(assistant.citations.length > 0, '服务器无引用，引用展示前提未满足')
    return { item, submitted, run, detail, assistant, doc }
  }
  const assertHistory = async (page, history) => {
    await openThread(page, history.item)
    await poll(async () => (await page.locator('.message').count()) === history.detail.messages.length, 7000, '消息历史未全部恢复')
    const actual = (await page.locator('.message').evaluateAll((items) => items.map((item) => ({ role: item.classList.contains('user') ? 'user' : 'assistant', content: item.querySelector('.message-content')?.textContent?.trim(), citations: Array.from(item.querySelectorAll('.citation')).map((node) => node.textContent?.trim()) })))).map((message) => ({ ...message, content: hash(message.content) }))
    // FE_010/013：比较Markdown可见正文的哈希；失败证据不输出其他用例的检索原文。
    const expected = history.detail.messages.map((message) => ({ role: message.role, content: hash(renderedText(message.content)), citations: message.citations.map((citation) => `${citation.filename} · ${citation.start_offset}-${citation.end_offset}`) }))
    assert.deepEqual(actual, expected, '浏览器消息/引用与服务端事实不一致')
    return { thread_id: history.item.thread_id, run_id: history.run.run_id, message_ids: history.detail.messages.map((message) => message.message_id), citation_count: history.assistant.citations.length }
  }

  try {
    // FE_001：HTTP、multipart与SSE真实经过Vite同源代理；独立API读取ID核对同一project。
    await s.check('FE_001', 'TP-FE-001', 'browser-http-upload-sse', '正常浏览器HTTP/上传/SSE同源到达本project并与正式API事实一致', () => withPage(async (page) => {
      const item = await ctx.thread(unique('FE_001', 'routing'))
      assert.equal(item.owner_id, ctx.context.owner_id)
      const requests = []
      page.on('request', (request) => { if (new URL(request.url()).pathname.startsWith('/api/v1/')) requests.push({ url: request.url(), method: request.method() }) })
      await openThread(page, item)
      const run = await send(page, item, 'FE_001安全路由问题')
      await poll(async () => requests.some((request) => new URL(request.url).pathname === `/api/v1/runs/${run.run_id}/events/stream`), 7000, '浏览器未发出SSE订阅')
      const uploadResponse = watchResponse(page, (response) => new URL(response.url()).pathname === '/api/v1/documents' && response.request().method() === 'POST')
      await page.locator('input[type=file]').setInputFiles({ name: `${unique('FE_001', 'routing')}.txt`, mimeType: 'text/plain', buffer: Buffer.from('FE_001安全路由证据') })
      const uploaded = await uploadResponse
      assert.equal(uploaded.status(), 201)
      const document = await uploaded.json()
      assert.equal((await ctx.detail(item.thread_id)).runs[0].run_id, run.run_id)
      assert.ok((await ctx.request('/api/v1/documents')).body.documents.some((doc) => doc.document_id === document.document_id))
      const frontendOrigin = new URL(ctx.args.FrontendUrl).origin
      assert.ok(requests.length >= 5)
      assert.ok(requests.every((request) => new URL(request.url).origin === frontendOrigin), 'HTTP或SSE绕过本次合法同源代理')
      return { thread_id: item.thread_id, run_id: run.run_id, document_id: document.document_id, request_targets: requests.map((request) => ({ method: request.method, path: new URL(request.url).pathname })) }
    }))

    await s.check('FE_001', 'TP-FE-002', 'browser-create-select', '页面创建服务端Thread，并在两个独立Thread间准确选择各自历史', () => withPage(async (page) => {
      const first = await prepareHistory('FE_001', 'selection-A')
      const second = await prepareHistory('FE_001', 'selection-B')
      await openThread(page, first.item)
      const createResponse = watchResponse(page, (response) => new URL(response.url()).pathname === '/api/v1/threads' && response.request().method() === 'POST')
      await page.getByRole('button', { name: '新建会话', exact: true }).click()
      const createdResponse = await createResponse
      assert.equal(createdResponse.status(), 201)
      const created = await createdResponse.json()
      assert.equal((await ctx.detail(created.thread_id)).thread.thread_id, created.thread_id)
      await poll(async () => (await page.locator('.thread-item.active').textContent())?.trim() === created.title, 7000)
      await assertHistory(page, first)
      await assertHistory(page, second)
      return { created_thread_id: created.thread_id, selected_thread_ids: [first.item.thread_id, second.item.thread_id], server_titles_visible: true }
    }))

    // FE_002：空工作区仅控制GET传输；提交、组件输入和禁用判断仍为真实生产逻辑。
    await s.check('FE_002', 'TP-FE-003', 'browser-no-thread', '未选择Thread时textarea/发送禁用，Ctrl+Enter不发起提交', () => withPage(async (page) => {
      let submitCount = 0
      page.on('request', (request) => { if (request.method() === 'POST' && /\/messages$/.test(new URL(request.url()).pathname)) submitCount++ })
      await page.route('**/api/v1/threads', (route) => route.request().method() === 'GET' ? route.fulfill({ status: 200, json: [] }) : route.continue())
      await page.goto(ctx.args.FrontendUrl, { waitUntil: 'domcontentloaded' })
      await page.locator('.thread-panel .empty-state').waitFor()
      assert.equal(await page.locator('textarea').isDisabled(), true)
      assert.equal(await page.getByRole('button', { name: '发送', exact: true }).isDisabled(), true)
      await page.locator('textarea').dispatchEvent('keydown', { key: 'Enter', ctrlKey: true })
      assert.equal(submitCount, 0)
      return { submit_count: submitCount, active_thread: null }
    }))
    await s.check('FE_002', 'TP-FE-003', 'browser-empty-input', '已选Thread但输入为空或仅空格时不能提交', () => withPage(async (page) => {
      const item = await ctx.thread(unique('FE_002', 'empty'))
      await openThread(page, item)
      let submits = 0
      page.on('request', (request) => { if (request.method() === 'POST' && request.url().includes(`/${item.thread_id}/messages`)) submits++ })
      for (const text of ['', '   ']) {
        await page.locator('textarea').fill(text)
        assert.equal(await page.getByRole('button', { name: '发送', exact: true }).isDisabled(), true)
        await page.locator('textarea').press('Control+Enter')
      }
      assert.equal(submits, 0)
      assert.equal((await ctx.detail(item.thread_id)).messages.length, 0)
      return { thread_id: item.thread_id, submit_count: submits }
    }))
    for (const mode of ['button', 'ctrl-enter']) await s.check('FE_002', 'TP-FE-003', `browser-${mode}`, '每次按钮或Ctrl+Enter仅一个请求、一条用户Message且角色正文准确', () => withPage(async (page) => {
      const item = await ctx.thread(unique('FE_002', mode))
      await openThread(page, item)
      let submits = 0
      page.on('request', (request) => { if (request.method() === 'POST' && new URL(request.url()).pathname === `/api/v1/threads/${item.thread_id}/messages`) submits++ })
      const question = `FE_002中文安全问题-${mode}`
      const submitted = await send(page, item, question, mode)
      await ctx.waitRun(submitted.run_id)
      const detail = await ctx.detail(item.thread_id)
      const users = detail.messages.filter((message) => message.role === 'user')
      assert.equal(submits, 1)
      assert.equal(users.length, 1)
      assert.equal(users[0].content, question)
      await poll(async () => (await page.locator('.message.user').count()) === 1, 7000, '页面未显示唯一user消息')
      assert.equal((await page.locator('.message.user .message-content').textContent()).trim(), question)
      assert.equal((await page.locator('.message.user .message-meta').textContent()).trim(), '你')
      return { thread_id: item.thread_id, run_id: submitted.run_id, user_message_id: users[0].message_id, submit_count: submits, visible_user_count: 1 }
    }))

    await s.check('FE_004', 'TP-FE-005', 'browser-no-refresh', 'API成功后不刷新页面即可显示相同最终正文/引用且恰一个assistant', () => withPage(async (page) => {
      const uploaded = await ctx.upload(`${unique('FE_004', 'evidence')}.txt`, 'FE_004安全证据：SesRAG持久化会话与可恢复任务。')
      assert.equal(uploaded.status, 201); assert.equal((await ctx.waitDoc(uploaded.body.document_id)).status, 'indexed')
      const item = await ctx.thread(unique('FE_004', 'answer'))
      await openThread(page, item)
      const submitted = await send(page, item, 'FE_004安全证据：SesRAG持久化会话与可恢复任务。')
      assert.equal((await ctx.waitRun(submitted.run_id)).status, 'succeeded')
      const assistant = (await ctx.detail(item.thread_id)).messages.find((message) => message.role === 'assistant' && message.run_id === submitted.run_id)
      assert.ok(assistant); assert.ok(assistant.citations.length > 0)
      await poll(async () => (await page.locator('.message.assistant').count()) === 1 && hash((await page.locator('.message.assistant .message-content').textContent()).trim()) === hash(renderedText(assistant.content)), 5000, '无刷新页面未自动显示持久最终答案，或重放增量污染最终正文')
      const citations = await page.locator('.message.assistant .citation').allTextContents()
      assert.deepEqual(citations.map((text) => text.trim()), assistant.citations.map((citation) => `${citation.filename} · ${citation.start_offset}-${citation.end_offset}`))
      return { thread_id: item.thread_id, run_id: submitted.run_id, assistant_message_id: assistant.message_id, citation_count: assistant.citations.length, page_refreshed: false }
    }))

    // FE_006：HTTP替身只把本次POST转到真实不存在Thread；稳定错误由真实API生成。
    await s.check('FE_006', 'TP-FE-007', 'browser-request-failure', '真实404请求失败在页面展示安全稳定提示且不误显示成功', () => withPage(async (page) => {
      const item = await ctx.thread(unique('FE_006', 'request-error'))
      await openThread(page, item)
      const missing = '00000000-0000-4000-8000-000000000000'
      await page.route(`**/api/v1/threads/${item.thread_id}/messages`, async (route) => {
        const response = await route.fetch({ url: new URL(`/api/v1/threads/${missing}/messages`, ctx.args.FrontendUrl).href })
        await route.fulfill({ response })
      })
      await page.locator('textarea').fill('FE_006安全失败问题')
      await page.getByRole('button', { name: '发送', exact: true }).click()
      await page.locator('.error-banner').waitFor()
      const text = (await page.locator('.error-banner').textContent()).trim()
      const api = await ctx.request(`/api/v1/threads/${missing}/messages`, { method: 'POST', body: { content: 'FE_006安全失败问题' } })
      assert.equal(api.status, 404)
      assert.equal(text, api.body.message ?? '请求失败：404')
      assert.ok(!/Traceback|postgres(?:ql)?:|Bearer\s|[A-Z]:[\\/]/i.test(text), '提示包含敏感实现信息')
      assert.equal((await ctx.detail(item.thread_id)).runs.length, 0)
      return { thread_id: item.thread_id, status: api.status, safe_message: text, submitted_run_count: 0 }
    }))

    await s.check('FE_007', 'TP-FE-008', 'browser-normal-timeline', '正常Run时间线按服务器seq排序且每seq只显示一次', () => withPage(async (page) => {
      const item = await ctx.thread(unique('FE_007', 'timeline'))
      await openThread(page, item)
      const submitted = await send(page, item, 'FE_007安全时间线问题')
      await ctx.waitRun(submitted.run_id)
      const serverEvents = await ctx.events(submitted.run_id)
      await poll(async () => (await page.locator('.event-seq').count()) === serverEvents.length, 7000, '页面时间线没有补齐服务器事件')
      const visible = (await page.locator('.event-seq').allTextContents()).map((text) => Number(text.trim()))
      assert.deepEqual(visible, serverEvents.map((event) => event.seq))
      assert.equal(new Set(visible).size, visible.length)
      return { thread_id: item.thread_id, run_id: submitted.run_id, seq: visible }
    }))

    // FE_009：首次HTTP历史交付为空使原生SSE读取真实PG首帧，避免Vite空body未flush导致前置假失败。
    await s.check('FE_009', 'TP-FE-010', 'browser-disconnect-no-cancel', '受控透传服务socket断开、首次HTTP历史交付为空：真实PG queued活动SSE断线不取消', () => withPausedWorker(() => withPage(async (page) => {
      await instrumentNativeStream(page)
      const control = await delayFirstHistoryDelivery(page)
      const item = await ctx.thread(unique('FE_009', 'network'))
      await openThread(page, item)
      return withRunRelay(page, item, async (getRelay) => {
      const submitted = await send(page, item, 'FE_009安全断网问题')
      const cursor = await activeStreamReady(page, submitted.run_id, control, 'no-cancel')
      const requests = []
      page.on('request', (request) => { if (new URL(request.url()).pathname.endsWith('/cancel')) requests.push(request.url()) })
      const relay = getRelay()
      const observations = await disconnectNativeStream(page, relay, submitted.run_id, 'no-cancel')
      await page.waitForTimeout(300)
      assert.equal(requests.length, 0)
      assert.equal((await ctx.run(submitted.run_id)).status, 'queued')
      return { run_id: submitted.run_id, before_status: 'queued', after_status: 'queued', cancel_requests: 0, last_processed_seq: cursor, native_disconnect: observations, transport_connections: relay.connections, transport_control: control, scope: '受控透传服务socket断开，非普通浏览器离线；首次HTTP历史交付为空，SSE真实PG字节原样透传；不代表running分片完整续流' }
      })
    })))

    await s.check('FE_009', 'TP-FE-010', 'browser-reconnect-entry', '受控透传服务socket断开、首次HTTP历史交付为空：真实PG queued流原生error后恢复连接及已处理seq游标', () => withPausedWorker(() => withPage(async (page) => {
      await instrumentNativeStream(page)
      const control = await delayFirstHistoryDelivery(page)
      const item = await ctx.thread(unique('FE_009', 'reconnect-entry'))
      await openThread(page, item)
      return withRunRelay(page, item, async (getRelay) => {
      const streams = []
      page.on('request', (request) => { const url = new URL(request.url()); if (url.origin === new URL(ctx.args.FrontendUrl).origin && /\/events\/stream$/.test(url.pathname)) streams.push({ path: url.pathname, after_seq: url.searchParams.get('after_seq'), last_event_id: request.headers()['last-event-id'] ?? null }) })
      const submitted = await send(page, item, 'FE_009安全重连入口问题')
      const cursor = await activeStreamReady(page, submitted.run_id, control, 'reconnect')
      const relay = getRelay()
      const count = relay.connections.length
      const observations = await disconnectNativeStream(page, relay, submitted.run_id, 'reconnect')
      assert.equal((await ctx.run(submitted.run_id)).status, 'queued', '断线后Run意外取消或终态，重连条件不成立')
      const reconnect = page.getByRole('button', { name: /重新连接|重连/ })
      if (await reconnect.count()) await reconnect.first().click()
      const beforeReconnect = ctx.evidence('fe/FE_009-reconnect-native-disconnect.json', { native_disconnect: observations, transport_connections: relay.connections, official_requests: streams, transport_control: control, scope: '受控服务socket断开；非普通浏览器离线' })
      await poll(async () => relay.connections.length > count, 7000, `真实活动SSE error后没有自动重连或可用的手动重连入口；真实断线证据：${beforeReconnect}`)
      const resumed = relay.connections.at(-1)
      assert.ok(Number(resumed.last_event_id ?? resumed.after_seq ?? 0) >= cursor, '重连未携带已处理seq游标')
      // 正确游标后的queued流暂时无新帧；放行真实Worker产生后续PG事件。
      // 确认原生重连接收后续帧；正常terminal关闭允许发生。
      const released = ctx.compose(['start', 'worker'], 30000)
      assert.equal(released.code, 0, 'FE_009重连后的Worker放行失败')
      await ctx.ready(20000)
      await ctx.waitRun(submitted.run_id)
      await poll(async () => page.evaluate(({ id, cursor }) => window.__feNativeStreams.some((stream) => stream.url.includes(`/runs/${id}/`) && stream.opened > 0 && stream.last_seq > cursor), { id: submitted.run_id, cursor }), 7000, '重连请求携带游标但未收到放行Worker后的真实PG事件')
      const finalEvents = await ctx.events(submitted.run_id)
      await poll(async () => (await page.locator('.event-seq').count()) === finalEvents.length, 7000, '重连后页面未补齐真实事件')
      assert.deepEqual((await page.locator('.event-seq').allTextContents()).map((text) => Number(text.trim())), finalEvents.map((event) => event.seq), '重连后的事件缺失、重复或乱序')
      return { run_id: submitted.run_id, last_processed_seq: cursor, official_requests: streams, transport_connections: relay.connections, native_disconnect: observations, transport_control: control, final_seq: finalEvents.map((event) => event.seq), scope: '受控透传服务socket断开，非普通浏览器离线；首次HTTP历史交付为空，SSE仍为真实PG原始字节；queued恢复放行不代表running分片完整续流' }
      })
    })))

    for (const [point, part] of [['TP-FE-011', 'fresh-context'], ['TP-FE-018', 'frontend-restart']]) await s.check('FE_010', point, part, '清浏览器内存/存储或重启本次frontend后，从API恢复同一消息、引用和文档且不重复提交', async () => {
      const history = await prepareHistory('FE_010', part, true)
      await withPage((page) => assertHistory(page, history))
      if (part === 'frontend-restart') {
        const restarted = ctx.compose(['restart', 'frontend'], 60000)
        assert.equal(restarted.code, 0, '本次frontend重启失败')
        await poll(async () => { try { return (await fetch(ctx.args.FrontendUrl, { signal: AbortSignal.timeout(1500) })).ok } catch { return false } }, 20000, '本次frontend重启后未就绪')
      }
      return withPage(async (page) => {
        let submitted = 0
        page.on('request', (request) => { if (request.method() === 'POST' && /\/messages$/.test(new URL(request.url()).pathname)) submitted++ })
        const summary = await assertHistory(page, history)
        const doc = page.locator('.document-item').filter({ hasText: history.doc.filename })
        await doc.waitFor()
        assert.equal((await doc.locator('small').textContent()).trim(), history.doc.status)
        assert.equal(submitted, 0)
        assert.equal((await ctx.detail(history.item.thread_id)).messages.length, history.detail.messages.length)
        return { ...summary, document_id: history.doc.document_id, document_status: history.doc.status, new_submission_count: submitted, frontend_restarted: part === 'frontend-restart' }
      })
    })

    await s.check('FE_011', 'TP-FE-012', 'browser-terminal-restore', '刷新并选择成功历史Thread后自动恢复对应Run状态与全部Event，不需新提问', () => withPage(async (page) => {
      const history = await prepareHistory('FE_011', 'terminal')
      const expectedEvents = await ctx.events(history.run.run_id)
      await assertHistory(page, history)
      await page.reload({ waitUntil: 'domcontentloaded' })
      await page.locator('.thread-item').filter({ hasText: history.item.title }).click()
      await poll(async () => (await page.locator('.run-panel').count()) === 1, 3000, '刷新仅恢复Message，未恢复Run状态/事件时间线')
      assert.equal((await page.locator('.run-panel strong').textContent()).trim(), history.run.status)
      assert.deepEqual((await page.locator('.event-seq').allTextContents()).map((text) => Number(text.trim())), expectedEvents.map((event) => event.seq))
      return { thread_id: history.item.thread_id, run_id: history.run.run_id, event_count: expectedEvents.length }
    }))

    // FE_012：上传响应初态与Worker终态各自核对，不把loading结束当索引完成。
    for (const branch of ['indexed', 'failed']) {
      for (const phase of ['initial', 'automatic-terminal']) await s.check('FE_012', 'TP-FE-013', `browser-${branch}-${phase}`, phase === 'initial' ? '上传响应的原名和初始状态准确显示' : 'API索引终态后不刷新自动显示indexed或failed及安全错误原因', () => withPage(async (page) => {
        const name = `${unique('FE_012', `${branch}-${phase}`)}.txt`
        const bytes = branch === 'indexed' ? Buffer.from('FE_012安全索引证据，Worker应处理为indexed。') : Buffer.alloc(0)
        const item = await ctx.thread(unique('FE_012', `${branch}-${phase}`))
        await openThread(page, item)
        const response = watchResponse(page, (result) => new URL(result.url()).pathname === '/api/v1/documents' && result.request().method() === 'POST')
        await page.locator('input[type=file]').setInputFiles({ name, mimeType: 'text/plain', buffer: bytes })
        const api = await response
        assert.equal(api.status(), 201)
        const uploaded = await api.json()
        const node = page.locator('.document-item').filter({ hasText: name })
        await node.waitFor()
        assert.equal(uploaded.filename, name)
        assert.equal((await node.locator('small').textContent()).trim(), uploaded.status)
        if (phase === 'initial') return { document_id: uploaded.document_id, filename: name, initial_status: uploaded.status }
        const final = await ctx.waitDoc(uploaded.document_id)
        assert.equal(final.status, branch)
        await poll(async () => (await node.locator('small').textContent()).trim() === final.status, 4000, `文档页面仍为${uploaded.status}，未自动更新为${final.status}`)
        if (branch === 'failed') { assert.ok(final.last_error_code); assert.ok((await node.textContent()).includes(final.last_error_code), 'failed文档未显示稳定错误原因') }
        return { document_id: final.document_id, initial_status: uploaded.status, final_status: final.status, last_error_code: final.last_error_code, page_refreshed: false }
      }))
    }

    await s.check('FE_013', 'TP-FE-014', 'browser-citation-label', '可见引用文件名与offset逐项等于最终Message真实引用', () => withPage(async (page) => {
      const history = await prepareHistory('FE_013', 'labels', true)
      return assertHistory(page, history)
    }))
    await s.check('FE_013', 'TP-FE-014', 'browser-citation-expand', '引用提供实际可展开交互并展示document/chunk及位置证据', () => withPage(async (page) => {
      const history = await prepareHistory('FE_013', 'expand', true)
      await assertHistory(page, history)
      const citation = page.locator('.citation').first()
      const interactive = await citation.evaluate((node) => node.matches('button, a, summary, [role=button]') || !!node.querySelector('button,a,summary,[role=button]') || node.hasAttribute('tabindex'))
      assert.equal(interactive, true, '引用只有静态标签，没有可展开入口')
      await citation.click()
      const expected = history.assistant.citations[0]
      await poll(async () => (await page.locator('.conversation-column').textContent()).includes(expected.chunk_id), 3000, '展开后未显示真实chunk证据身份')
      assert.ok((await page.locator('.conversation-column').textContent()).includes(expected.document_id))
      return { run_id: history.run.run_id, document_id: expected.document_id, chunk_id: expected.chunk_id, expanded: true }
    }))

    // FE_014：浏览器观察三个独立健康展示，缺失本身是实现失败；不以源码grep宣布通过。
    await s.check('FE_014', 'TP-FE-016', 'browser-health-panels', '页面独立展示API/Worker/DB事实健康且区分ready/degraded/unknown', () => withPage(async (page) => {
      const ready = await ctx.request('/health/ready')
      assert.equal(ready.status, 200)
      await page.goto(ctx.args.FrontendUrl, { waitUntil: 'domcontentloaded' })
      await page.locator('.topbar').waitFor()
      // 每个候选必须是实际状态控件，不能让回答或文档名里的Worker/DB文字冒充健康面板。
      const states = await page.locator('.connection-dot, .health-panel, .health-item, .health-status, [data-health-component], [role=status]').allTextContents()
      const missing = ['API', 'Worker', 'DB'].filter((label) => !states.some((text) => new RegExp(label === 'DB' ? 'DB|数据库|PostgreSQL' : label, 'i').test(text) && /ready|degraded|unknown/.test(text)))
      assert.deepEqual(missing, [], `健康面板缺少独立事实展示：${missing.join('/')}`)
      assert.ok(states.length >= 3, '页面未提供三个独立健康对象')
      return { api_status: ready.body.status, worker_status: ready.body.worker, database_status: ready.body.database, panels_present: true }
    }))

    // FE组件真正失败仍逐项导出；收集不到任何一项时逐项失败，不把工具启动当产品通过。
    s.note('FE组件阶段：挂载真实Workspace/stores/components，HTTP/SSE替身仅提供精确传输时序。')
    const rawPath = path.join(ctx.args.RuntimeDir, `fe-vitest-result-${invocation}.json`)
    const child = spawnSync(process.execPath, [path.join(smokeRoot, 'node_modules/vitest/vitest.mjs'), 'run', '--config', path.join(smokeRoot, 'vitest.config.mjs'), 'specific_test_script/fe-workspace.test.ts', '--reporter=json', `--outputFile=${rawPath}`], { cwd: smokeRoot, encoding: 'utf8', timeout: 45000, maxBuffer: 4 * 1024 * 1024, windowsHide: true })
    let result
    try { result = JSON.parse(fs.readFileSync(rawPath, 'utf8')) } catch { result = undefined }
    const assertions = result?.testResults?.flatMap((item) => item.assertionResults ?? []) ?? []
    for (const definition of componentChecks) {
      const [id, point, sub, expected] = definition
      await s.check(id, point, sub, expected, async () => {
        const assertion = assertions.find((item) => item.title === componentTitle(definition))
        assert.ok(assertion, `Vitest未产生本项结果；子进程退出=${child.status ?? '无'}，工具错误=${child.error?.code ?? '无'}；这不是产品通过`)
        const failures = (assertion.failureMessages ?? []).map((message) => message.split(/\r?\n/)[0]).join('；')
        assert.equal(assertion.status, 'passed', `真实生产组件断言${assertion.status}：${redact(failures, ctx.secrets)}`)
        return { vitest_title: assertion.title, status: assertion.status, duration_ms: assertion.duration, scope: '真实前端组件，受控HTTP/SSE传输，不代替真实慢Provider/PG竞态验收' }
      })
    }

    // 缺少完整慢Provider/PG屏障的子项保留独立限制，组件失败不会被blocked覆盖。
    const pending = [
      ['FE_003', 'TP-FE-004', 'persistent-slow-stream', '持久首片到达且第二片等待时显示增量', '未接入真实慢Provider/Worker持久化分片屏障；已有真实组件断言验证前端缺失'],
      ['FE_005', 'TP-FE-006', 'persistent-state-stages', '真实queued/running/terminal各阶段与页面一致', '无真实运行中屏障，Mock运行过快无法可靠抓取所有阶段；受控真实组件阶段已逐项执行'],
      ['FE_005', 'TP-FE-015', 'persistent-running-cancel-race', '运行中页面取消后无迟到成功', '无Worker模型/最终提交竞争屏障，组件取消请求不证明后端竞态'],
      ['FE_006', 'TP-FE-007', 'persistent-permanent-failure', '真实永久失败Run的原因在页面展示', '未提供本次隔离Worker永久失败Provider驱动；真实组件异步failed投影已独立断言'],
      ['FE_008', 'TP-FE-009', 'persistent-replay-overlap', '持久replay/SSE交界不重复最终正文', '未提供真实Worker分片与replay/SSE屏障；真实组件同seq重叠与历史最终Message已独立断言'],
      ['FE_009', 'TP-FE-010', 'persistent-active-network-resume', '真实running分片期间断网追加事件并恢复补放', '缺真实慢Run分片屏障；queued受控传输服务断开与组件检查不能代替running分片完整续流'],
      ['FE_009', 'TP-FE-010', 'ordinary-browser-offline', '普通浏览器离线真正断开已建立的SSE并恢复补放', 'Chromium setOffline对已建立空闲SSE未触发原生error，普通离线前置不足；受控透传socket断开子项不能代替此场景'],
      ['FE_011', 'TP-FE-012', 'persistent-active-reload', '真实queued/running刷新后续订至终态', '无真实活动Run屏障；terminal恢复与真实组件活动恢复已独立断言'],
      ['FE_014', 'TP-FE-016', 'health-fault-states', 'API/Worker/DB故障健康在页面分别展示', '页面健康组件缺失；完整故障态动态展示待产品补齐后准备对应服务故障条件'],
      ['FE_015', 'TP-FE-017', 'persistent-delayed-thread-switch', '真实A首片暂停切B后放行A不串Thread且可切回', '无真实持久慢Run屏障；真实Workspace组件旧流关闭与B投影隔离已独立断言'],
    ]
    for (const [id, point, sub, expected, reason] of pending) s.block(id, point, sub, expected, reason)
  } finally { await browser?.close() }
})
