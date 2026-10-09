import { runCategory, assert } from '../lib/category-kit.mjs';
import { uuid, lazy, isTime, runFacts, stoppedWorker, successful, eventSummary } from './run-test-driver.mjs';

export const coveredCases = ['CAN_001', 'CAN_002', 'CAN_003', 'CAN_004', 'CAN_005', 'CAN_006'];
await runCategory('can', async s => {
  const ctx = s.ctx;
  // CAN_001：queued取消与各终态重复取消独立验证，不以Index失败代替Run失败。
  const cancelled = lazy(() => stoppedWorker(ctx, async () => {
    const thread = await ctx.thread('CAN_001 queued取消');
    const submitted = await ctx.submit(thread.thread_id, 'CAN_001 排队取消问题', uuid());
    assert.equal((await ctx.run(submitted.run_id)).status, 'queued');
    const response = await ctx.request(`/api/v1/runs/${submitted.run_id}/cancel`, { method: 'POST' });
    return { thread, submitted, response, api: await ctx.run(submitted.run_id), facts: runFacts(ctx, submitted.run_id), detail: await ctx.detail(thread.thread_id), events: await ctx.events(submitted.run_id) };
  }));
  await s.check('CAN_001', 'TP-CAN-001', 'queued_cancel_transaction', 'queued取消200；Run/Task cancelled、cancel_requested_at有值且只有1条run.cancelled，无assistant', async () => {
    const data = await cancelled(); assert.equal(data.response.status, 200); assert.equal(data.response.body.status, 'cancelled');
    assert.equal(data.api.status, 'cancelled'); assert.equal(data.api.task.state, 'cancelled');
    assert.equal(data.facts.status, 'cancelled'); assert.equal(data.facts.task_state, 'cancelled'); assert.ok(isTime(data.facts.cancel_requested_at));
    assert.equal(data.facts.assistant_message_id, null); assert.equal(data.detail.messages.filter(message => message.role === 'assistant').length, 0);
    assert.equal(data.events.filter(event => event.type === 'run.cancelled').length, 1);
    assert.deepEqual(data.events.map(event => event.type), ['run.created', 'task.queued', 'run.cancelled']);
    return { run_id: data.submitted.run_id, task_id: data.submitted.task_id, cancel_requested_at: data.facts.cancel_requested_at, events: eventSummary(data.events) };
  });
  await s.check('CAN_001', 'TP-CAN-001', 'restart_does_not_claim_cancelled', '恢复Worker后已取消Task不领取、不回答，原Run和Task保持cancelled', async () => {
    const data = await cancelled();
    // CAN_001：独立哨兵Run确认Worker至少经过一个领取周期，不用固定sleep推断已处理。
    const sentinel = await successful(ctx, 'CAN_001 取消后的工作周期');
    assert.equal(sentinel.run.status, 'succeeded');
    const facts = runFacts(ctx, data.submitted.run_id); assert.equal(facts.status, 'cancelled'); assert.equal(facts.task_state, 'cancelled');
    assert.equal(facts.attempt, 0); assert.equal(facts.generation, 0); assert.equal(facts.assistant_message_id, null);
    assert.ok(JSON.stringify(await ctx.events(data.submitted.run_id)) === JSON.stringify(data.events), '恢复Worker不得改变取消事实');
    assert.equal((await ctx.detail(data.thread.thread_id)).messages.length, 1);
    return { run_id: facts.run_id, task_id: facts.task_id, attempt: facts.attempt, generation: facts.generation, worker_cycle_observed: sentinel.run.run_id };
  });
  await s.check('CAN_001', 'TP-CAN-002', 'cancelled_repeat', '已cancelled Run重复取消不改状态、取消时间、错误或Event，不创建assistant', async () => {
    const data = await cancelled(); const before = runFacts(ctx, data.submitted.run_id); const oldEvents = await ctx.events(data.submitted.run_id);
    const response = await ctx.request(`/api/v1/runs/${data.submitted.run_id}/cancel`, { method: 'POST' });
    assert.equal(response.status, 200); assert.equal(response.body.status, 'cancelled');
    assert.deepEqual(runFacts(ctx, data.submitted.run_id), before); assert.ok(JSON.stringify(await ctx.events(data.submitted.run_id)) === JSON.stringify(oldEvents), '重复取消不得改变Event');
    return { run_id: data.submitted.run_id, terminal_status: 'cancelled', event_count: oldEvents.length, unchanged: true };
  });
  await s.check('CAN_001', 'TP-CAN-002', 'succeeded_repeat', '已succeeded Run取消保持成功、原正文/引用/错误/指针及Event完全不变', async () => {
    const data = await successful(ctx, 'CAN_001 成功终态重复取消'); const before = runFacts(ctx, data.run.run_id);
    const response = await ctx.request(`/api/v1/runs/${data.run.run_id}/cancel`, { method: 'POST' });
    assert.equal(response.status, 200); assert.equal(response.body.status, 'succeeded');
    assert.deepEqual(runFacts(ctx, data.run.run_id), before); assert.ok(JSON.stringify(await ctx.events(data.run.run_id)) === JSON.stringify(data.events), '成功后的取消不得改变Event');
    assert.ok(JSON.stringify((await ctx.detail(data.thread.thread_id)).messages) === JSON.stringify(data.detail.messages), '成功后的取消不得改变Message');
    return { run_id: data.run.run_id, terminal_status: 'succeeded', assistant_message_id: data.run.assistant_message_id, unchanged: true };
  });
  s.block('CAN_001', 'TP-CAN-002', 'failed_repeat', '已failed Run取消保持失败、错误和事件不变', 'E2 真实Run永久失败驱动尚未准备；空文Index失败不是Run失败');
  s.blockCase('CAN_002', 'E2 query embedding返回前屏障及search调用计数驱动尚未准备');
  s.blockCase('CAN_003', 'E2 search完成后、model.stream_answer调用前屏障及调用计数驱动尚未准备');
  s.blockCase('CAN_004', 'E2 首片已提交、后两片在取消后返回的慢Provider逐片屏障尚未准备');
  for (const sub of ['cancel_commits_first', 'success_commits_first']) s.block('CAN_005', 'TP-CAN-006', sub, '控制取消/最终成功提交先后，每Run只有一个有效终态，无迟到覆盖', `E2 ${sub}最终SELECT/commit双事务屏障尚未准备`);
  s.blockCase('CAN_006', 'E2 真实临时失败、到期回排与取消交错驱动尚未准备；不得SQL写retry_waiting伪造前提');
});
