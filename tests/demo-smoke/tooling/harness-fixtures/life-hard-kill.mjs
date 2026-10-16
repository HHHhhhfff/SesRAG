import { Context, parseArgs, assert, poll } from '../../lib/category-kit.mjs'
import { withFrontendHarness } from '../frontend-harness.mjs'

// 父runner在真实浏览器/SSE/Worker屏障后硬杀整树；容器登记由CleanupRunId恢复。
const ctx = new Context(parseArgs())
await withFrontendHarness(ctx, async h => {
  const thread = await h.api.thread('LIFE hard kill')
  const run = await h.api.submit(thread.thread_id, '生命周期中断探针')
  await h.page.goto(h.frontendUrl)
  await h.page.locator('.thread-item').filter({ hasText: thread.title }).click()
  await h.controller.start('delta'); await h.controller.awaitReached()
  const facts = await h.controller.facts(run.run_id)
  assert.ok(facts.events.some(row => row.type === 'answer.delta'))
  await poll(async () => (await h.page.locator('body').innerText()).includes('第一片'), 15000)
  ctx.evidence('life/hard-kill-armed.json', { run_id: run.run_id, controller: h.controller.resource, owner_pid: process.pid, facts_observed: true })
  process.stdout.write('HARD_KILL_ARMED\n')
  await new Promise(resolve => setTimeout(resolve, 90000))
  throw new Error('硬杀哨兵未被终止')
})
