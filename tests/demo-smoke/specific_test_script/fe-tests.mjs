import { createHash, randomUUID } from 'node:crypto'
import { JSDOM } from 'jsdom'
import { marked } from '../../../frontend/node_modules/marked/lib/marked.esm.js'
import { runCategory, assert, poll } from '../lib/category-kit.mjs'

import { registeredBrowser } from '../tooling/frontend-resources.mjs'
import { runFrontendComponents } from '../tooling/frontend-components.mjs'
import { runPersistentFrontend, runLegacyDisconnectChecks } from '../tooling/frontend-persistent.mjs'

export const coveredCases = ['FE_001', 'FE_002', 'FE_003', 'FE_004', 'FE_005', 'FE_006', 'FE_007', 'FE_008', 'FE_009', 'FE_010', 'FE_011', 'FE_012', 'FE_013', 'FE_014', 'FE_015']

// FE全部用例：正式业务经六参数隔离环境；FE_009受控本地SSE透传只允许本例Run和Origin，不禁用CORS。
await runCategory('fe', async (s) => {
  const ctx = s.ctx
  const invocation = randomUUID().slice(0, 8)
  const browser = await registeredBrowser(ctx)
  const withPage = fn => browser.withPage(fn)
  const unique = (id, part) => `${id}-${part}-${ctx.args.RunId}-${invocation}`
  const renderedText = (content) => JSDOM.fragment(marked.parse(content)).textContent.trim()
  const hash = (text) => createHash('sha256').update(text).digest('hex')
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
      assert.ok(text.includes(api.body.code), '错误提示未显示正式稳定错误码')
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

    // FE_009：保留既有两个目标ID，以真实running断线场景各自重新执行。
    await runLegacyDisconnectChecks(s)

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
      const states = await page.locator('.health-panel > span').allTextContents()
      const missing = ['API', 'Worker', 'DB'].filter((label) => !states.some((text) => new RegExp(label === 'DB' ? 'PG|DB|数据库|PostgreSQL' : label, 'i').test(text) && /ready|degraded|unknown/.test(text)))
      assert.deepEqual(missing, [], `健康面板缺少独立事实展示：${missing.join('/')}`)
      assert.ok(states.length >= 3, '页面未提供三个独立健康对象')
      return { api_status: ready.body.status, worker_status: ready.body.worker, database_status: ready.body.database, panels_present: true }
    }))

    await runFrontendComponents(s)
    await runPersistentFrontend(s)
    s.block('FE_009', 'TP-FE-010', 'ordinary-browser-offline', '普通浏览器离线真正断开已建立SSE并恢复补放', 'ADR002明确暂缓：Chromium setOffline不可靠断开已建立SSE；受控socket场景不替代普通离线')
  } finally { await browser?.close() }
})
