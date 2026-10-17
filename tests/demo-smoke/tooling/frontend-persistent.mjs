import { assert, poll, execute } from '../lib/category-kit.mjs'
import { withFrontendHarness } from './frontend-harness.mjs'
import { frontendResource } from './frontend-resources.mjs'
import { createSseRelay } from '../specific_test_script/fe-sse-transport.mjs'

export const persistentChecks = [
  ['FE_003', 'TP-FE-004', 'persistent-slow-stream', '真实首片已PG提交，第二片暂停时显示草稿，终态后唯一最终正文'],
  ['FE_005', 'TP-FE-006', 'persistent-state-stages', 'queued/running/succeeded页面与API和PG逐阶段一致'],
  ['FE_005', 'TP-FE-015', 'persistent-running-cancel-race', '运行中页面取消准确Run，无迟到成功且停止按钮消失'],
  ['FE_006', 'TP-FE-007', 'persistent-permanent-failure', '真实永久失败稳定码在页面展示且敏感异常哨兵不泄露'],
  ['FE_008', 'TP-FE-009', 'persistent-replay-overlap', '延迟真实replay与SSE同seq交叠不重复，最终历史不翻倍'],
  ['FE_009', 'TP-FE-010', 'persistent-active-network-resume', '首片后真socket断开，离线期间PG继续完成，游标补放无遗漏且不取消'],
  ['FE_011', 'TP-FE-012', 'persistent-active-reload', '活跃Run刷新重新选择后自动续订至终态，无新提交'],
  ['FE_014', 'TP-FE-016', 'health-fault-states', 'API/Worker/PG/Redis独立真实故障在页面显示，逐项恢复'],
  ['FE_015', 'TP-FE-017', 'persistent-delayed-thread-switch', 'A首片切B再放行A不串会话，切回读取A最终历史'],
]

const gate = () => { let release; const promise = new Promise(resolve => { release = resolve }); return { promise, release } }
const finalText = '第一片第二片第三片'

// FE_015：只校验读取的观测对象；负哨兵不得写回页面、HTTP或PG事实。
export function assertThreadRunPanel(observation, expected) {
  assert.equal(observation.run_id, expected.run_id, 'B面板混入其他Run身份')
  assert.equal(observation.status, expected.status, 'B面板状态与正式事实不一致')
  assert.equal(observation.visible_status, expected.status, 'B可见状态与正式事实不一致')
  assert.deepEqual(observation.events, expected.events, 'B面板事件身份/seq/type与完整Journal不一致')
  assert.deepEqual(observation.visible_events, expected.events.map(({ seq, type }) => ({ seq, type })), 'B可见时间线与完整Journal不一致')
}

async function observeThreadRunPanel(h, runId, excludedRunId) {
  const apiRun = await h.api.run(runId)
  const apiEvents = await h.api.events(runId)
  const facts = await h.controller.facts(runId)
  assert.equal(apiRun.run_id, runId)
  assert.equal(apiRun.status, 'cancelled')
  assert.equal(facts.run.status, 'cancelled')
  assert.equal(facts.task.state, 'cancelled')
  const expected = { run_id: runId, status: apiRun.status,
    events: apiEvents.map(({ run_id, seq, type }) => ({ run_id, seq, type })) }
  assert.deepEqual(facts.events.map(({ run_id, seq, type }) => ({ run_id, seq, type })), expected.events)
  let observation
  await poll(async () => {
    if (await h.page.locator('.run-panel').count() !== 1) return false
    observation = await h.page.locator('.run-panel').evaluate(node => {
      // RunTimeline根DOM关联的Vue props仅只读取身份；可见状态/时间线另外逐项核对。
      const props = node.__vueParentComponent.props
      return { run_id: props.run?.run_id, status: props.run?.status,
        events: props.events.map(({ run_id, seq, type }) => ({ run_id, seq, type })),
        visible_status: node.querySelector('strong')?.textContent?.trim(),
        visible_events: Array.from(node.querySelectorAll('.event-list li')).map(item => ({
          seq: Number(item.querySelector('.event-seq')?.textContent), type: item.querySelector('span:last-child')?.textContent?.trim(),
        })) }
    })
    try { assertThreadRunPanel(observation, expected); return true } catch { return false }
  }, 10000, 'B的Run身份/状态/完整事件未恢复或残留A投影')
  assert.notEqual(observation.run_id, excludedRunId)
  assert.ok(observation.events.every(event => event.run_id !== excludedRunId))
  return { api_run: apiRun, pg_facts: facts, api_events: expected.events, panel: observation, excluded_run_id: excludedRunId }
}
async function select(page, item) {
  await page.locator('.thread-item').filter({ hasText: item.title }).click()
  await poll(async () => (await page.locator('.topbar h2').textContent()) === item.title, 10000)
}
async function open(h, title) {
  const item = await h.api.thread(title)
  await h.page.goto(h.frontendUrl, { waitUntil: 'domcontentloaded' })
  await select(h.page, item)
  return item
}
async function send(h, item) {
  const response = h.page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === `/api/v1/threads/${item.thread_id}/messages`)
  void response.catch(() => {})
  await h.page.locator('textarea').fill('持久浏览器安全问题')
  await h.page.getByRole('button', { name: '发送', exact: true }).click()
  const result = await response
  assert.equal(result.status(), 201)
  return result.json()
}
async function state(h, runId, expected) {
  await poll(async () => (await h.page.locator('.run-panel strong').textContent())?.trim() === expected, 12000)
  const facts = await h.controller.facts(runId)
  assert.equal(facts.run.status, expected)
  assert.equal((await h.api.run(runId)).status, expected)
  return facts
}
async function partial(h, runId) {
  await h.controller.awaitReached()
  const facts = await h.controller.facts(runId)
  assert.equal(facts.run.status, 'running')
  assert.equal(facts.events.filter(e => e.type === 'answer.delta').length, 1)
  assert.equal(facts.messages.filter(m => m.role === 'assistant').length, 0)
  await poll(async () => (await h.page.locator('.message.assistant .message-content').textContent())?.trim() === '第一片', 12000)
  return facts
}
async function complete(h, item, runId) {
  const facts = await poll(async () => { const f = await h.controller.facts(runId); return f.run.status === 'succeeded' ? f : null }, 12000)
  await state(h, runId, 'succeeded')
  const detail = await h.api.detail(item.thread_id)
  const answers = detail.messages.filter(m => m.role === 'assistant')
  assert.equal(answers.length, 1); assert.equal(answers[0].content, finalText)
  await poll(async () => (await h.page.locator('.message.assistant').count()) === 1 && (await h.page.locator('.message.assistant .message-content').textContent())?.trim() === finalText, 10000)
  const expected = (await h.api.events(runId)).map(e => e.seq)
  await poll(async () => (await h.page.locator('.event-seq').count()) === expected.length, 10000)
  assert.deepEqual((await h.page.locator('.event-seq').allTextContents()).map(Number), expected)
  assert.equal(new Set(expected).size, expected.length)
  assert.equal(facts.messages.filter(m => m.role === 'user').length, 1)
  assert.equal(facts.messages.filter(m => m.role === 'assistant').length, 1)
  return facts
}
async function nativeStream(page) {
  // FE_009：只记录原生事件和close，不调用回调，不生成帧。
  await page.addInitScript(() => {
    const Native = window.EventSource
    window.__feStreams = []
    window.EventSource = class extends Native {
      constructor(url, options) {
        super(url, options)
        this.trace = { url: String(url), opened: 0, errors: 0, seq: [], closed: false }
        window.__feStreams.push(this.trace)
        this.addEventListener('open', () => this.trace.opened++)
        this.addEventListener('error', () => this.trace.errors++)
        for (const type of ['answer.delta', 'run.started', 'run.succeeded']) this.addEventListener(type, event => this.trace.seq.push(Number(event.lastEventId)))
      }
      close() { this.trace.closed = true; super.close() }
    }
  })
}

async function flow(h, sub) {
  const { page, api, controller } = h
  await nativeStream(page)
  const item = await open(h, sub)
  const evidence = { thread_id: item.thread_id, stages: [] }
  let cancels = 0, posts = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/cancel')) cancels++
    if (request.method() === 'POST' && request.url().endsWith('/messages')) posts++
  })
  if (sub === 'persistent-permanent-failure') {
    const run = await send(h, item)
    await controller.start('failure')
    await poll(async () => (await api.run(run.run_id)).status === 'failed', 15000)
    evidence.final = await state(h, run.run_id, 'failed')
    assert.equal(evidence.final.run.last_error_code, 'TEST_PROVIDER_FAILURE')
    assert.equal(evidence.final.task.attempt, 1)
    const dom = await page.locator('body').textContent()
    assert.ok(dom.includes('TEST_PROVIDER_FAILURE'))
    const sentinels = ['fe-secret-sentinel', 'fe-user', 'fe-password', 'fe-private', 'fe-raw-response']
    evidence.sensitive_hits = sentinels.map(value => dom.includes(value))
    assert.ok(evidence.sensitive_hits.every(hit => !hit))
    assert.equal(evidence.final.messages.filter(m => m.role === 'assistant').length, 0)
    return evidence
  }

  let replayCount = 0, heldReplay, replayDelivered = false, replayRelease = gate(), relay, relayRow
  const relayStreams = []
  let networkHold = false
  const networkRelease = gate()
  try {
    if (sub === 'persistent-replay-overlap') {
      // 第二次HTTP补放与SSE同时开启；真实Worker首片持久后截取真实响应，再延迟交付。
      await page.route('**/events?*', async route => {
        replayCount++
        if (replayCount !== 2) return route.fallback()
        await controller.start('delta'); await controller.awaitReached()
        const response = await route.fetch()
        heldReplay = await response.json()
        await replayRelease.promise
        await route.fulfill({ response })
        replayDelivered = true
      })
    }
    if (sub === 'persistent-active-network-resume') {
      await page.route('**/events/stream?*', async route => {
        const row = frontendResource(api, 'sse', { url: route.request().url(), via: 'registered-sse-relay' })
        row.running(); relayStreams.push(row)
        if (networkHold) await networkRelease.promise
        const input = new URL(route.request().url())
        if (!relay) {
          relayRow = frontendResource(api, 'sse-relay')
          relay = await createSseRelay({ baseUrl: api.args.BaseUrl, frontendUrl: h.frontendUrl, runId: input.pathname.split('/')[4], lifetimeMs: 60000 })
          relayRow.running({ origin: relay.origin, run_id: input.pathname.split('/')[4] })
        }
        await route.fulfill({ status: 302, headers: { Location: relay.origin + input.pathname + input.search } })
      })
      await page.route('**/events?*', async route => { if (networkHold) await networkRelease.promise; await route.fallback() })
    }
    const run = await send(h, item)
    evidence.run_id = run.run_id
    if (sub !== 'persistent-replay-overlap') {
      evidence.stages.push(await state(h, run.run_id, 'queued'))
      if (sub === 'persistent-active-reload') {
        await page.reload({ waitUntil: 'domcontentloaded' }); await select(page, item)
        evidence.queued_restored = await state(h, run.run_id, 'queued')
        assert.equal(posts, 1)
      }
      await controller.start('delta')
    }
    evidence.partial = await partial(h, run.run_id)
    evidence.stages.push(await state(h, run.run_id, 'running'))

    if (sub === 'persistent-running-cancel-race') {
      const cancelled = page.waitForResponse(r => new URL(r.url()).pathname === `/api/v1/runs/${run.run_id}/cancel`)
      void cancelled.catch(() => {})
      await page.getByRole('button', { name: '停止', exact: true }).click()
      assert.equal((await cancelled).status(), 200)
      await controller.release()
      await poll(async () => (await api.run(run.run_id)).status === 'cancelled', 12000)
      evidence.final = await state(h, run.run_id, 'cancelled')
      await controller.stop()
      evidence.after_worker_exit = await controller.facts(run.run_id)
      assert.equal(evidence.after_worker_exit.task.state, 'cancelled')
      assert.equal(evidence.after_worker_exit.events.filter(e => e.type === 'run.cancelled').length, 1)
      assert.equal(evidence.after_worker_exit.events.filter(e => e.type === 'run.succeeded').length, 0)
      assert.equal(evidence.after_worker_exit.messages.filter(m => m.role === 'assistant').length, 0)
      assert.equal(await page.getByRole('button', { name: '停止', exact: true }).count(), 0)
      assert.equal(cancels, 1)
      return evidence
    }
    if (sub === 'persistent-replay-overlap') {
      await poll(async () => heldReplay, 10000)
      const delta = heldReplay.events.find(e => e.type === 'answer.delta')
      assert.ok(delta)
      await poll(async () => page.evaluate(seq => window.__feStreams.some(stream => stream.seq.includes(seq)), delta.seq), 8000)
      evidence.overlap_seq = delta.seq
      replayRelease.release()
      await poll(async () => replayDelivered, 5000)
      await poll(async () => (await page.locator('.message.assistant .message-content').textContent())?.trim() === '第一片', 5000)
    }
    if (sub === 'persistent-active-network-resume') {
      await poll(async () => relay?.connections.some(c => c.forwarded_bytes > 0 && !c.closed), 10000)
      evidence.cursor = Math.max(...(await page.locator('.event-seq').allTextContents()).map(Number))
      networkHold = true
      evidence.severed = relay.disconnect()
      await poll(async () => page.evaluate(() => window.__feStreams.some(s => s.errors > 0)), 8000)
      await controller.release()
      evidence.offline_final = await poll(async () => { const f = await controller.facts(run.run_id); return f.run.status === 'succeeded' ? f : null }, 12000)
      assert.ok(evidence.offline_final.events.some(e => e.seq > evidence.cursor && e.type === 'answer.delta'))
      assert.equal((await page.locator('.message.assistant .message-content').textContent()).trim(), '第一片')
      networkHold = false; networkRelease.release()
      await poll(async () => relay.connections.length > 1, 10000)
      assert.ok(Number(relay.connections[1].after_seq ?? relay.connections[1].last_event_id) >= evidence.cursor)
      evidence.relay = relay.connections
    }
    if (sub === 'persistent-active-reload') {
      await page.reload({ waitUntil: 'domcontentloaded' }); await select(page, item)
      evidence.restored = await state(h, run.run_id, 'running')
      await partial(h, run.run_id)
      assert.equal(posts, 1)
      await poll(async () => page.evaluate(() => window.__feStreams.length > 0), 8000)
    }
    if (sub === 'persistent-delayed-thread-switch') {
      const other = await api.thread('B独立历史')
      const bRun = await api.submit(other.thread_id, 'B事实用户历史')
      await api.request(`/api/v1/runs/${bRun.run_id}/cancel`, { method: 'POST', body: {} })
      // B通过正式API持久化独立用户历史；重载列表后重新选择A确认首片再切B。
      await page.reload({ waitUntil: 'domcontentloaded' }); await select(page, item); await partial(h, run.run_id)
      await select(page, other)
      evidence.b_run_id = bRun.run_id
      evidence.b_before_a_release = await observeThreadRunPanel(h, bRun.run_id, run.run_id)
      await controller.release()
      await poll(async () => (await api.run(run.run_id)).status === 'succeeded', 12000)
      evidence.b_after_a_terminal = await observeThreadRunPanel(h, bRun.run_id, run.run_id)
      const bDetail = await api.detail(other.thread_id)
      assert.equal((await page.locator('.topbar h2').textContent()), other.title)
      assert.ok(!(await page.locator('.conversation-column').textContent()).includes(finalText))
      assert.equal(await page.locator('.message.assistant').count(), 0)
      assert.equal(bDetail.messages.length, 1)
      evidence.b_thread_id = other.thread_id
      evidence.old_streams = await page.evaluate(id => window.__feStreams.filter(s => s.url.includes(id)), run.run_id)
      assert.ok(evidence.old_streams.every(s => s.closed))
      await select(page, item)
    }
    await controller.release()
    evidence.final = await complete(h, item, run.run_id)
    if (sub === 'persistent-replay-overlap') {
      await page.reload({ waitUntil: 'domcontentloaded' }); await select(page, item)
      evidence.final_history = await complete(h, item, run.run_id)
      evidence.real_replay_delivered = replayDelivered
    }
    assert.equal(cancels, 0)
    assert.equal(posts, 1)
    evidence.cancel_requests = cancels
    return evidence
  } finally {
    replayRelease.release(); networkRelease.release()
    if (relay) {
      await relay.close(); assert.ok(relay.connections.every(c => c.closed))
      relayRow.closed({ observed_connections_closed: true, connections: relay.connections })
      for (const row of relayStreams) row.closed({ observed_connections_closed: true })
    }
  }
}

async function health(ctx, h) {
  const { page, controller } = h
  const observations = []
  await controller.start('production')
  const read = async expected => {
    await poll(async () => {
      const response = page.waitForResponse(r => new URL(r.url()).pathname === '/health/ready')
      void response.catch(() => {})
      await page.getByRole('button', { name: '检查健康', exact: true }).click()
      await response
      const text = await page.locator('.health-panel').textContent()
      ctx.evidence('fe/health-progress.json', { observations, awaiting: expected, last_panel: text })
      return expected.every(value => text.includes(value))
    }, 15000, `健康页面未进入${expected.join('/')}`)
    const response = await h.api.request('/health/ready')
    const text = await page.locator('.health-panel').textContent()
    assert.ok(!/Traceback|Bearer|postgresql:|fe-secret|fe-private/.test(await page.locator('body').textContent()))
    observations.push({ expected, response: response.body, safe_dom: true, text: text.trim() })
  }
  await page.goto(h.frontendUrl, { waitUntil: 'domcontentloaded' })
  await poll(async () => {
    const body = (await h.api.request('/health/ready')).body
    ctx.evidence('fe/health-initial.json', { body, controller: await controller.status() })
    return body.worker === 'ready'
  }, 15000, '控制器真实Worker readiness未就绪')
  await read(['API ready', 'PG ready', 'Worker ready', 'Redis ready'])
  // FE_014：精确本run服务标签校验后才允许停依赖；每次故障均finally恢复。
  const serviceAction = (service, action) => {
    const ids = ctx.compose(['ps', '-a', '-q', service], 15000)
    assert.equal(ids.code, 0); assert.ok(ids.stdout.trim())
    const inspect = execute('docker', ['inspect', ids.stdout.trim(), '--format', '{{json .Config.Labels}}'])
    assert.equal(inspect.code, 0)
    const labels = JSON.parse(inspect.stdout)
    assert.equal(labels['com.docker.compose.project'], ctx.context.compose_project)
    assert.equal(labels['com.docker.compose.service'], service)
    const result = ctx.compose([action, service], 45000)
    assert.equal(result.code, 0)
  }
  try { await h.closeGateway(); await read(['API unknown', 'PG unknown', 'Worker unknown', 'Redis unknown']) }
  finally { await h.openGateway() }
  await read(['API ready', 'PG ready', 'Worker ready', 'Redis ready'])
  try { await controller.stop(); await read(['PG ready', 'Worker unknown', 'Redis ready']) }
  finally { await controller.start('production') }
  await poll(async () => (await h.api.request('/health/ready')).body.worker === 'ready', 15000)
  await read(['API ready', 'PG ready', 'Worker ready', 'Redis ready'])
  try { serviceAction('postgres', 'stop'); await read(['API unavailable', 'PG unavailable']) }
  finally { serviceAction('postgres', 'start') }
  await poll(async () => (await h.api.request('/health/ready')).body.database === 'ready', 20000)
  await read(['API ready', 'PG ready', 'Redis ready'])
  try { serviceAction('redis', 'stop'); await read(['API degraded', 'PG ready', 'Redis degraded', 'Worker unknown']) }
  finally { serviceAction('redis', 'start') }
  await poll(async () => (await h.api.request('/health/ready')).body.worker === 'ready', 20000)
  await read(['API ready', 'PG ready', 'Worker ready', 'Redis ready'])
  return { observations }
}

export async function runPersistentFrontend(s, only = undefined) {
  for (const [id, tp, sub, expected] of persistentChecks) {
    if (only && !only.split(',').includes(sub)) continue
    await s.check(id, tp, sub, expected, async () => withFrontendHarness(s.ctx, async h => {
      const data = sub === 'health-fault-states' ? await health(s.ctx, h) : await flow(h, sub)
      const evidence = s.ctx.evidence(`fe/${sub}.json`, data)
      return { thread_id: data.thread_id, run_id: data.run_id, evidence, observations: data.observations?.length, safe_dom: data.sensitive_hits?.every(hit => !hit) }
    }))
  }
}

export async function runLegacyDisconnectChecks(s) {
  for (const sub of ['browser-disconnect-no-cancel', 'browser-reconnect-entry']) {
    await s.check('FE_009', 'TP-FE-010', sub, '真实running首片后socket断开不取消，恢复带游标并完整补放', async () => withFrontendHarness(s.ctx, async h => {
      const data = await flow(h, 'persistent-active-network-resume')
      const evidence = s.ctx.evidence(`fe/${sub}.json`, data)
      return { run_id: data.run_id, cursor: data.cursor, cancel_requests: data.cancel_requests, evidence }
    }))
  }
}
