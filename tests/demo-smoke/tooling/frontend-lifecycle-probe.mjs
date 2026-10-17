import fs from 'node:fs'
import path from 'node:path'
import { Context, parseArgs, assert, poll } from '../lib/category-kit.mjs'
import { withFrontendHarness } from './frontend-harness.mjs'

// LIFE_006消费用探针：真实首片/SSE/浏览器已存在后故意抛错，核验finally的实际关闭。
// 此工具仅验证生命周期，不能作为FE产品用例通过。
const ctx = new Context(parseArgs())
const sentinel = 'frontend-intentional-body-failure'
let observed = false
try {
  await withFrontendHarness(ctx, async h => {
    const item = await h.api.thread('生命周期异常安全会话')
    const run = await h.api.submit(item.thread_id, '生命周期安全问题')
    await h.page.goto(h.frontendUrl, { waitUntil: 'domcontentloaded' })
    await h.page.locator('.thread-item').filter({ hasText: item.title }).click()
    await h.controller.start('delta'); await h.controller.awaitReached()
    await poll(async () => (await h.page.locator('.message.assistant .message-content').textContent())?.trim() === '第一片', 10000)
    const facts = await h.controller.facts(run.run_id)
    assert.equal(facts.run.status, 'running')
    assert.equal(facts.events.filter(e => e.type === 'answer.delta').length, 1)
    ctx.evidence('fe/lifecycle-armed.json', { owner_pid: process.pid, run_id: run.run_id, facts, controller_resource: h.controller.resource })
    throw new Error(sentinel)
  })
} catch (error) {
  if (error.message !== sentinel) throw error
  observed = true
}
assert.equal(observed, true)
const registry = JSON.parse(fs.readFileSync(path.join(ctx.args.RuntimeDir, 'frontend-resources.json'), 'utf8'))
const own = registry.resources.filter(row => row.owner_pid === process.pid)
assert.ok(own.some(row => row.kind === 'sse'))
assert.ok(own.every(row => row.status === 'closed'))
for (const row of own.filter(row => row.kind === 'browser')) {
  assert.equal(row.observed_browser_disconnected, true)
  assert.throws(() => process.kill(row.pid, 0))
}
ctx.evidence('fe/lifecycle-exception-cleanup.json', { intentional_body_failure: observed, resources: own, browser_pids_absent: true })
console.log('真实running首片后故意异常：页面/Context/Chromium PID/SSE/网关/Vite/控制器均finally关闭')
