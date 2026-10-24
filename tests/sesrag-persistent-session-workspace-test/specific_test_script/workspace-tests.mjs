import fs from 'node:fs';
import { openCategory, helper } from '../tooling/product-category.mjs';
import { assert, key, thread, detail, request, send, answer, done, scenario, barrier, release, events, run, until, observations, cancelledSource } from './support.mjs';
import { openBrowser, openPage, waitTitle, waitText, selectThread, assertEventsUnique, assertUnavailableModel, pageRunId } from './browser-support.mjs';
import { upload } from './compatibility-runtime.mjs';
import { terminalSamples, nextChatSequence } from './run-evidence-runtime.mjs';

async function main(contextFile) {
  const suite = openCategory('workspace', contextFile); const c = suite.context; const browser = await openBrowser();
  const fresh = (id) => thread(c, `${id}-${key().slice(0, 8)}`);
  async function pageFor(item, action, bid, extras) {
    const session = await openPage(browser, c, item, bid, extras);
    try { return await action(session.page, session.session); }
    finally { await session.session.close(); }
  }
  try {
    // UI_001：页面归档、无偏好和有效归档偏好三个独立浏览器会话。
    await suite.test('UI_001', async () => {
      const t = await fresh('UI_001'); await answer(c, t, '归档历史');
      await pageFor(t, async (page) => {
        await waitText(page, '归档历史'); await page.getByRole('button', { name: '归档会话', exact: true }).click();
        await until(() => page.locator('textarea').isDisabled(), Boolean, '归档只读');
        assert.ok((await page.locator('.thread-item').filter({ hasText: t.title }).innerText()).includes('已归档'));
        assert.equal(await page.getByRole('button', { name: '从此处分支' }).count(), 0);
      });
      await fresh('UI_001普通');
      await pageFor(null, async (page) => { await until(() => page.locator('.topbar h2').textContent(), (value) => value !== '选择会话', '无偏好默认选择'); assert.notEqual(await page.locator('.topbar h2').textContent(), t.title); });
      await pageFor(t, async (page) => { assert.equal(await page.locator('textarea').isDisabled(), true); await page.getByRole('button', { name: '取消归档', exact: true }).click(); await until(() => page.locator('textarea').isEnabled(), Boolean, '取消归档可写'); await waitText(page, '归档历史'); });
      return { actual: '页面归档保留历史并禁写；无偏好默认普通视图，有效归档偏好恢复到归档只读视图；取消归档回普通视图并可继续。', thread_id: t.thread_id };
    });
    // UI_002：真实刷新、失效身份和不可写Storage不能成为事实来源。
    await suite.test('UI_002', async () => {
      const t = await fresh('UI_002'); const created = await answer(c, t, '刷新持久事实'); const before = await detail(c, t.thread_id);
      await pageFor(t, async (page) => { await waitText(page, '刷新持久事实'); await page.reload(); await waitTitle(page, t.title); await waitText(page, '刷新持久事实'); assert.equal(await pageRunId(page), created.run_id); });
      await pageFor({ thread_id: key(), title: undefined }, async (page) => { await until(() => page.locator('.topbar h2').textContent(), (value) => value !== '选择会话', '失效偏好回落'); });
      await pageFor(t, async (page) => { await waitText(page, '刷新持久事实'); }, t.default_branch_id, { invalidStorage: true, savedModel: '{bad' });
      assert.deepEqual((await detail(c, t.thread_id)).messages, before.messages);
      return { actual: '刷新后正文/Run来自服务端；不存在的Thread偏好回落有效会话；损坏模型偏好和不可写Storage未阻断页面。', run_id: created.run_id };
    });
    // UI_003：Provider真实停顿时刷新，必须完整补建首段草稿而不发业务写请求。
    await suite.test('UI_003', async () => {
      const states = [];
      const queuedThread = await fresh('UI_003-queued'); let queued;
      await helper(c, 'stop', 'worker');
      try {
        queued = await send(c, queuedThread, 'QUEUED_REFRESH_INPUT');
        assert.equal((await run(c, queued.run_id)).status, 'queued');
        await pageFor(queuedThread, async (page) => {
          await waitText(page, 'QUEUED_REFRESH_INPUT'); const writes = []; page.on('request', (req) => { if (req.method() === 'POST') writes.push(req.url()); });
          await page.reload(); await waitTitle(page, queuedThread.title); assert.equal(await pageRunId(page), queued.run_id);
          await until(() => page.locator('.run-panel .section-heading strong').textContent(), (value) => value === 'queued', 'queued刷新状态'); assert.deepEqual(writes, []);
        });
      } finally { await helper(c, 'start', 'worker'); }
      assert.equal((await done(c, queued.run_id)).status, 'succeeded'); states.push({ state: 'queued', run_id: queued.run_id });
      const t = await fresh('UI_003'); await scenario(c, { kind: 'stall', chunks: ['REFRESH_DRAFT', '最终后缀'] });
      const created = await send(c, t, '刷新活动Run', 'ws-http-a'); const held = await barrier(c);
      try {
        await pageFor(t, async (page) => {
          await waitText(page, 'REFRESH_DRAFT'); const writes = []; page.on('request', (req) => { if (req.method() === 'POST') writes.push(new URL(req.url()).pathname); });
          await page.reload(); await waitText(page, 'REFRESH_DRAFT'); assert.equal(await pageRunId(page), created.run_id); assert.deepEqual(writes, []);
        });
      } finally { await release(c, held); }
      await done(c, created.run_id); const page = await detail(c, t.thread_id);
      assert.equal(page.messages.filter((item) => item.role === 'assistant').length, 1);
      states.push({ state: 'running', run_id: created.run_id });
      const retryThread = await fresh('UI_003-retry'); await scenario(c, { kind: 'partial-disconnect', chunks: ['OLD_REFRESH_DELTA'], request_seq: await nextChatSequence(c) }); let retry;
      await pageFor(retryThread, async (page) => {
        retry = await send(c, retryThread, 'RETRY_REFRESH_INPUT', 'ws-http-a');
        await until(() => run(c, retry.run_id), (item) => item.status === 'retry_waiting', '真实重试等待窗口', 15000);
        try {
          await helper(c, 'stop', 'worker'); assert.equal((await run(c, retry.run_id)).status, 'retry_waiting', '必须在重试领取前停Worker保持窗口');
          assert.ok((await events(c, retry.run_id)).some((event) => event.type === 'answer.delta' && event.data.text.includes('OLD_REFRESH_DELTA')));
          const writes = []; page.on('request', (req) => { if (req.method() === 'POST') writes.push(req.url()); });
          await page.reload(); await waitTitle(page, retryThread.title); assert.equal(await pageRunId(page), retry.run_id);
          await until(() => page.locator('.run-panel .section-heading strong').textContent(), (value) => value === 'retry_waiting', '刷新确实取回retry_waiting而非后续终态'); assert.deepEqual(writes, []);
        } finally { await helper(c, 'start', 'worker'); }
      });
      const retried = await done(c, retry.run_id); assert.equal(retried.status, 'succeeded'); assert.equal(retried.task.attempt, 2);
      const retryPage = await detail(c, retryThread.thread_id); assert.equal(retryPage.messages.filter((item) => item.role === 'assistant').length, 1); assert.ok(!retryPage.messages.at(-1).content.includes('OLD_REFRESH_DELTA')); states.push({ state: 'retry_waiting', run_id: retry.run_id }); await scenario(c);
      for (const item of [queuedThread, t, retryThread]) await pageFor(item, async (page) => { await until(() => page.locator('.message.assistant').count(), (count) => count === 1, '恢复后的唯一最终DOM'); });
      return { actual: 'queued/running/retry_waiting三个独立样本刷新均沿用原Run/Task/input；running草稿由Journal完整重建，无重复业务POST，每组最终唯一assistant。', states };
    });
    // UI_004：实际网络中断到自动重连耗尽，再使用现有人工恢复按钮。
    await suite.test('UI_004', async () => {
      const t = await fresh('UI_004'); await scenario(c, { kind: 'stall', chunks: ['RECONNECT_HEAD', 'RECONNECT_TAIL'] });
      const created = await send(c, t, '断线补放', 'ws-http-a'); const held = await barrier(c);
      try {
        const journal = await events(c, created.run_id); assert.ok(journal.length >= 3);
        const shuffled = [journal[2], journal[0], journal[2]]; let reads = 0; const streamCursors = [];
        await pageFor(t, async (page) => {
          await until(() => streamCursors.length, (value) => value >= 2, '缺口后的重连');
          assert.equal(streamCursors[1], 1, '游标不能跳过未收到的seq2');
          await waitText(page, 'RECONNECT_HEAD'); await assertEventsUnique(page);
        }, undefined, { beforeNavigate: async (page) => {
          await page.route((url) => url.pathname === `/api/v2/runs/${created.run_id}/events`, async (route) => {
            const response = await route.fetch(); const body = await response.json();
            await route.fulfill({ response, json: ++reads <= 2 ? { ...body, events: shuffled, has_more: false } : body });
          });
          await page.route('**/events/stream*', async (route) => {
            streamCursors.push(Number(new URL(route.request().url()).searchParams.get('after_seq')));
            if (streamCursors.length === 1) await route.fulfill({ status: 200, contentType: 'text/event-stream', body: shuffled.map((event) => `id: ${event.seq}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join('') });
            else await route.continue();
          });
        } });
        await pageFor(t, async (page) => {
          await page.route('**/events/stream*', (route) => route.abort('connectionfailed'));
          await page.reload(); await until(() => page.locator('.stream-status').innerText(), (value) => value.includes('连接中断'), '有限自动重连耗尽', 20000);
          assert.ok(await page.getByRole('button', { name: '重新连接', exact: true }).isVisible());
          await page.unroute('**/events/stream*'); await page.getByRole('button', { name: '重新连接', exact: true }).click();
          await waitText(page, 'RECONNECT_HEAD'); await assertEventsUnique(page);
        });
      } finally { await release(c, held); }
      const finished = await done(c, created.run_id); assert.equal(finished.task.attempt, 1);
      return { actual: '真实Journal重排/重复/缺seq2的传输注入后游标停1并重连补齐；另组三次失败后人工恢复，seq/字符无重复；同一Run/Task仅执行一次。', run_id: created.run_id };
    });
    // UI_005：真实HTTP响应被网络屏障延迟，切换后才释放。
    await suite.test('UI_005', async () => {
      const a = await fresh('UI_005A'); const b = await fresh('UI_005B'); await answer(c, a, 'OLD_SCOPE_A'); await answer(c, b, 'CURRENT_SCOPE_B');
      const arun = (await detail(c, a.thread_id)).recent_run_id;
      const anchor = (await detail(c, a.thread_id)).messages[0].message_id;
      const sibling = (await request(c, `/api/v2/threads/${a.thread_id}/branches`, { method: 'POST', headers: { 'Idempotency-Key': key() }, body: { parent_branch_id: a.default_branch_id, fork_message_id: anchor }, expected: 201 })).data;
      await answer(c, a, 'CURRENT_SCOPE_BRANCH_B', 'mock-default', sibling.branch_id);
      const branchRun = (await detail(c, a.thread_id, sibling.branch_id)).recent_run_id; const threadRun = (await detail(c, b.thread_id)).recent_run_id;
      const observations = [];
      for (const scope of ['thread', 'branch']) for (const suffix of ['thread', 'run', 'context', 'events', 'stream']) for (const fail of [false, true]) {
        const target = scope === 'thread' ? b : { ...a, default_branch_id: sibling.branch_id };
        await pageFor(target, async (page) => {
          let releaseResponse; const gate = new Promise((resolve) => { releaseResponse = resolve; }); let seen = false; let intercepted = false; let handlerError;
          let handledResolve; const handled = new Promise((resolve) => { handledResolve = resolve; });
          const path = suffix === 'thread' ? `/api/v2/threads/${a.thread_id}` : `/api/v2/runs/${arun}${{ run: '', context: '/context', events: '/events', stream: '/events/stream' }[suffix]}`;
          const matches = (url) => url.pathname === path && (suffix !== 'thread' || scope !== 'branch' || !url.searchParams.has('branch_id'));
          await page.route(matches, async (route) => {
            if (intercepted) { await route.continue(); return; } intercepted = true;
            try { const response = await route.fetch(); seen = true; await gate;
              await route.fulfill(fail ? { status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'OLD_SCOPE_FAILURE', message: '合成旧响应失败' }) } : { response });
            } catch (error) { handlerError = error; seen = true; } finally { handledResolve(); }
          });
          const branchSelect = page.locator('.workspace-controls select').first();
          try {
            if (scope === 'thread') await page.locator('.thread-item').filter({ hasText: a.title }).click(); else await branchSelect.selectOption(a.default_branch_id);
            await until(() => seen, Boolean, `挂起A的${suffix}`);
            if (scope === 'thread') await selectThread(page, b);
            else {
              if (suffix === 'thread') {
                // 详情加载时产品确实移除分支控件；用真实store action驱动第二选择，不能虚构一个仍可点击的控件。
                await page.evaluate(async ({ tid, bid }) => { const { useThreadStore } = await import('/src/stores/thread.ts'); await useThreadStore().selectThread(tid, bid); }, { tid: a.thread_id, bid: sibling.branch_id });
              } else await branchSelect.selectOption(sibling.branch_id);
              await until(() => branchSelect.inputValue(), (value) => value === sibling.branch_id, '选回兄弟路径');
            }
          }
          finally { releaseResponse(); if (intercepted) await Promise.race([handled, new Promise((_, reject) => setTimeout(() => reject(new Error('迟到响应handler结束超时')), 20000))]); await page.unroute(matches); }
          if (handlerError) throw handlerError;
          await waitText(page, scope === 'thread' ? 'CURRENT_SCOPE_B' : 'CURRENT_SCOPE_BRANCH_B');
          if (scope === 'thread') assert.ok(!(await page.locator('.message-list').innerText()).includes('OLD_SCOPE_A')); else assert.equal(await branchSelect.inputValue(), sibling.branch_id);
          await waitTitle(page, target.title);
          assert.equal(await pageRunId(page), scope === 'thread' ? threadRun : branchRun);
          assert.ok(!(await page.locator('body').innerText()).includes('OLD_SCOPE_FAILURE'));
          observations.push({ scope, endpoint: suffix, response: fail ? '503' : 'success', selected_thread: target.thread_id });
        });
      }
      return { actual: '跨Thread及同Thread兄弟路径两种作用域、五层接口、迟到成功/失败共20组网络屏障；B选择、消息、错误和身份均不被旧A响应覆盖。', observations };
    });
    // UI_006：真实预算计划与DOM提示对应；不在测试中伪造ContextPlan。
    await suite.test('UI_006', async () => {
      const results = [];
      for (const variant of ['none', 'trim', 'summary', 'over']) {
        const t = await fresh(`UI_006-${variant}`);
        if (['trim', 'summary'].includes(variant)) for (let index = 0; index < (variant === 'summary' ? 2 : 1); index++) await answer(c, t, 'UI_CONTEXT_PRIVATE_SOURCE ' + 'old '.repeat(1200));
        // 冻结mock-small可用1664；系统+空输入计16。1648词恰好占满，摘要无空间；1649词超限。
        const content = variant === 'trim' ? 'q '.repeat(1648) : variant === 'over' ? 'q '.repeat(1649) : '当前短问题';
        const created = await send(c, t, content, 'mock-small'); const finished = await done(c, created.run_id); const plan = finished.context_plan;
        assert.ok(plan, `${variant}缺真实规划`);
        if (variant === 'none') { assert.equal(plan.omitted_message_count, 0); assert.equal(plan.summary_count, 0); }
        if (variant === 'trim') { assert.ok(plan.omitted_message_count > 0); assert.equal(plan.summary_count, 0); }
        if (variant === 'summary') assert.ok(plan.summary_count > 0);
        if (variant === 'over') { assert.equal(finished.status, 'failed'); assert.equal(plan.status, 'budget_exceeded'); }
        await pageFor(t, async (page) => {
          for (const reload of [false, true]) {
            if (reload) { await page.reload(); await waitTitle(page, t.title); }
            await until(() => page.locator('.context-notice').innerText(), (value) => value.includes('上下文：'), '真实上下文提示');
            const text = await page.locator('.context-notice').innerText();
            assert.ok(text.includes(`${plan.estimated_input_tokens}/${plan.context_window_tokens}`)); assert.ok(text.includes(`裁剪 ${plan.omitted_message_count} 条`)); assert.ok(text.includes(`摘要 ${plan.summary_count} 条`));
            assert.ok(!text.includes('UI_CONTEXT_PRIVATE_SOURCE')); if (variant === 'over') assert.ok(text.includes('预算超限'));
            const safe = (await request(c, `/api/v2/runs/${created.run_id}/context`)).data.plan;
            await until(() => page.locator('.context-detail').innerText(), (value) => value.includes(safe.counter_version), '计划安全详情');
            const detailText = await page.locator('.context-detail').innerText(); assert.ok(!detailText.includes('UI_CONTEXT_PRIVATE_SOURCE'));
            for (const range of safe.omitted_ranges) assert.ok(detailText.includes(`${range.from_seq}–${range.to_seq}`));
            for (const summary of safe.summaries) assert.ok(detailText.includes(`${summary.from_seq}–${summary.to_seq}`));
          }
        }); results.push({ variant, run_id: created.run_id, plan });
      }
      return { actual: '无裁剪/只裁剪/摘要/预算超限四组实际规划与刷新DOM逐项对应四预算、数量、来源范围和策略；提示未暴露历史/摘要/证据全文。', results };
    });
    // UI_007：页面事件身份/顺序必须取自当前Run Journal。
    await suite.test('UI_007', async () => {
      const samples = await terminalSamples(c, 'UI_007'); const results = [];
      for (const sample of samples) await pageFor(sample.thread, async (page) => {
        assert.equal(await pageRunId(page), sample.created.run_id);
        await until(() => page.locator('.event-seq').count(), (count) => count === sample.journal.length, '完整真实时间线'); const seq = await assertEventsUnique(page);
        assert.deepEqual(seq, sample.journal.map((item) => item.seq));
        const visible = await page.locator('.event-list').innerText(); assert.ok(visible.includes(`run.${sample.finished.status}`)); assert.ok(!visible.includes('tool.call')); assert.ok(!visible.includes('chain_of_thought'));
        if (sample.kind === 'retry') assert.ok(visible.includes('task.retry_scheduled')); if (sample.kind === 'cancel') assert.ok(visible.includes('run.cancelling'));
        const progress = await page.locator('.run-progress').innerText(); assert.ok(progress.includes(`第 ${sample.finished.task.attempt} 次尝试`)); assert.ok(progress.includes(`generation ${sample.finished.task.generation}`));
        await selectThread(page, samples.find((other) => other !== sample).thread); await selectThread(page, sample.thread); assert.equal(await pageRunId(page), sample.created.run_id);
        results.push({ kind: sample.kind, run_id: sample.created.run_id, event_count: seq.length });
      });
      return { actual: '成功/永久失败/自动重试/取消四组真实时间线全部按Run/seq对应Journal，attempt/generation和终态明确，切换后恢复正确；无隐藏思维或虚构工具。', results };
    });
    // UI_008/009：内容经正式产品请求持久化，再由真实Chromium执行DOM安全检查。
    async function markdown(id, malicious) {
      const t = await fresh(id); const text = malicious ? fs.readFileSync(new URL('../fixtures/documents/history-sentinel.md', import.meta.url), 'utf8') + '\n<script>window.WS_XSS=1</script><img src="x" onerror="window.WS_XSS=2"><svg onload="window.WS_XSS=3"></svg>\n[危险](javascript:window.WS_XSS=4)\n[危险data](data:text/html,<script>alert(1)</script>)' : '# 标题\n\n段落 **加粗** 与 `inline`\n\n- 列表项\n\n[合法](#safe)\n\n```js\nconst value = 1;\n```';
      await scenario(c, { kind: 'stall', chunks: [text.slice(0, Math.ceil(text.length / 2)), text.slice(Math.ceil(text.length / 2))] });
      const created = await send(c, t, text, 'ws-http-a'); const held = await barrier(c);
      try {
        await pageFor(t, async (page) => {
          const dialogs = []; page.on('dialog', async (dialog) => { dialogs.push(dialog.type()); await dialog.dismiss(); });
          await waitText(page, malicious ? 'HISTORY' : '标题');
          const unsafe = await page.locator('.message-list').evaluate((root) => [...root.querySelectorAll('*')].filter((item) => item.tagName === 'SCRIPT' || [...item.attributes].some((attr) => /^on/i.test(attr.name)) || /^(javascript:|data:text\/html)/i.test(item.getAttribute('href') ?? '')).length);
          assert.equal(unsafe, 0); assert.equal(await page.evaluate(() => window.WS_XSS), undefined); assert.deepEqual(dialogs, []);
        });
      } finally { await release(c, held); }
      await done(c, created.run_id); const saved = await detail(c, t.thread_id); assert.equal(saved.messages[0].content, text); assert.equal(saved.messages.at(-1).content, text.trim());
      await pageFor(t, async (page) => { await until(() => page.locator('.message.assistant').count(), (count) => count === 1, '唯一最终DOM'); if (!malicious) { assert.ok(await page.locator('.message.assistant h1').isVisible()); assert.equal(await page.locator('.message.assistant pre code').count(), 1); } else {
        assert.equal(await page.locator('.message-list script,.message-list [onerror],.message-list [onclick],.message-list [onload],.message-list a[href^="javascript:"],.message-list a[href^="data:"]').count(), 0);
        const before = page.url(); await page.locator('.message-list').evaluate((root) => { for (const element of root.querySelectorAll('a,img,svg')) { element.dispatchEvent(new Event('error')); element.dispatchEvent(new MouseEvent('click', { bubbles: true })); } });
        assert.equal(page.url(), before); assert.equal(await page.evaluate(() => window.WS_XSS), undefined);
      } });
      return { actual: malicious ? '用户及assistant两方向恶意文本持久原文不变；真实流式/最终DOM无脚本、事件属性或危险协议，执行哨兵/弹窗均未触发。' : '用户及assistant Markdown在真实DOM呈现标题/列表/链接/行内码/跨delta代码块；最终只有一条回答，持久层保留Markdown原文。', run_id: created.run_id };
    }
    await suite.test('UI_008', () => markdown('UI_008', false));
    await suite.test('UI_009', () => markdown('UI_009', true));
    // UI_010：两个真实Run回答与当前引用投影不能串用。
    await suite.test('UI_010', async () => {
      const a = await fresh('UI_010A'); const b = await fresh('UI_010B'); await answer(c, b, 'NEW_SCOPE_B');
      const documentA = await upload(c, 'UI_010-A.txt', 'EVIDENCE-WORKSPACE-A 本机虚构资料。');
      await answer(c, a, '引用A资料');
      const documentC = await upload(c, 'UI_010-C.txt', 'EVIDENCE-WORKSPACE-C 另一份虚构资料。');
      const target = await fresh('UI_010C'); await answer(c, target, '引用C资料');
      const expectedC = (await detail(c, target.thread_id)).messages.at(-1).citations;
      assert.ok(expectedC.some((citation) => citation.document_id === documentC.document_id));
      await scenario(c, { kind: 'stall', chunks: ['OLD_DRAFT_A', '尾部'] });
      const created = await send(c, a, '旧草稿会话', 'ws-http-a'); const held = await barrier(c);
      try { await pageFor(a, async (page) => {
        await waitText(page, 'OLD_DRAFT_A'); assert.ok(await page.locator('.citation').count());
        await selectThread(page, b); await waitText(page, 'NEW_SCOPE_B'); assert.equal(await page.locator('.citation').count(), 0); assert.ok(!(await page.locator('.message-list').innerText()).includes('OLD_DRAFT_A'));
        await selectThread(page, target); await waitText(page, '引用C资料'); assert.equal(await page.locator('.citation').count(), expectedC.length);
        await page.locator('.citation').first().click(); assert.ok(await page.locator('.citation-detail').isVisible());
        assert.ok(expectedC.every((citation) => [documentA.document_id, documentC.document_id].includes(citation.document_id)));
      }); }
      finally { await release(c, held); }
      await done(c, created.run_id);
      return { actual: 'A真实草稿/引用切到无引用B后均不残留，再切C仅显示其实际Message引用集合；同owner合法共享检索不误判为缓存串线。', run_id: created.run_id, expected_c_citations: expectedC };
    });
    // UI_011：实际模型选择改变请求快照，运行中控件禁用。
    await suite.test('UI_011', async () => {
      const t = await fresh('UI_011'); await scenario(c, { model: 'ws-http-b', kind: 'stall', chunks: ['MODEL_B', '回答'] });
      let held;
      try { await pageFor(t, async (page) => {
        const select = page.locator('.workspace-controls select').nth(1); await select.selectOption('ws-http-b:1');
        await page.locator('textarea').fill('选择模型B'); await page.getByRole('button', { name: '发送', exact: true }).click(); held = await barrier(c, 'ws-http-b');
        assert.equal(await select.isDisabled(), true); const rid = await pageRunId(page); const saved = await run(c, rid); assert.equal(saved.model.profile_id, 'ws-http-b');
        await release(c, held); held = null; await done(c, rid); await until(() => select.isEnabled(), Boolean, '终态模型解锁');
      }); } finally { if (held) await release(c, held); }
      await pageFor(t, async (page) => { assert.equal(await page.locator('.workspace-controls select').nth(1).inputValue(), 'mock-default:1'); }, undefined, { savedModel: JSON.stringify({ profile_id: 'missing-profile', version: 99 }) });
      await pageFor(t, async (page) => {
        const select = page.locator('.workspace-controls select').nth(1); assert.equal(await select.inputValue(), 'ws-http-b:1'); await scenario(c);
        await select.selectOption('ws-http-a:1'); await page.locator('textarea').fill('终态换为A'); await page.getByRole('button', { name: '发送', exact: true }).click();
        const current = await until(() => pageRunId(page), async (rid) => (await run(c, rid)).model.profile_id === 'ws-http-a', '换A后的真实Run');
        assert.equal((await done(c, current)).model.profile_id, 'ws-http-a');
      }, undefined, { savedModel: JSON.stringify({ profile_id: 'ws-http-b', version: 1 }) });
      try {
        const disabled = await helper(c, 'disable-profile'); assert.ok(disabled.result.includes('ws-http-b|disabled'), 'SQL必须实际更新目标Profile');
        const models = (await request(c, '/api/v2/models')).data; const expected = models.models.find((model) => model.profile_id === 'ws-http-b');
        assert.equal(expected.status, 'disabled', '禁用后正式API应立即返回disabled');
        await pageFor(t, async (page) => {
          const observed = { api: expected, browser: await assertUnavailableModel(page, 'ws-http-b:1', 'MODEL_PROFILE_DISABLED') };
          suite.evidence('UI_011-disabled-profile.json', observed);
        });
      }
      finally { await helper(c, 'restore-profile'); }
      return { actual: 'B实际执行与运行禁用、终态换A新Run、有效/失效模型偏好及真实PG禁用Profile的页面不可选说明均已验证；未存凭据。' };
    });
    // UI_012：真实成功后的regenerate按钮只创建一个关联Run，旧事实仍可读。
    await suite.test('UI_012', async () => {
      const t = await fresh('UI_012'); const source = await answer(c, t, '按钮来源'); let target;
      await pageFor(t, async (page) => {
        await until(() => page.getByRole('button', { name: '重新生成', exact: true }).isVisible(), Boolean, '重新生成按钮');
        const calls = []; page.on('request', (req) => { if (req.method() === 'POST' && req.url().endsWith('/regenerate')) calls.push(req.url()); });
        let free; const gate = new Promise((resolve) => { free = resolve; }); let entered = false; let handlerDone;
        const handled = new Promise((resolve) => { handlerDone = resolve; });
        await page.route(`**/runs/${source.run_id}/regenerate`, async (route) => { try { const response = await route.fetch(); entered = true; await gate; await route.fulfill({ response }); } finally { handlerDone(); } });
        const action = page.getByRole('button', { name: '重新生成', exact: true });
        try { await action.click(); await until(() => entered, Boolean, '关联操作已接受但响应挂起'); const pendingButton = page.getByRole('button', { name: '重试原操作', exact: true }); assert.equal(await pendingButton.isDisabled(), true); await pendingButton.evaluate((button) => button.click()); assert.equal(calls.length, 1); }
        finally { free(); if (entered) await handled; }
        target = await until(() => pageRunId(page), (id) => id !== source.run_id, '新关联Run'); assert.equal(calls.length, 1);
      });
      assert.equal((await done(c, target)).status, 'succeeded'); assert.equal((await run(c, source.run_id)).status, 'succeeded'); assert.equal((await run(c, target)).parent_run_id, source.run_id); assert.equal((await run(c, target)).model.profile_id, 'mock-default');
      const stopped = await fresh('UI_012-stop'); await scenario(c, { kind: 'stall', chunks: ['停止前草稿', '迟到答案'] });
      const active = await send(c, stopped, '按钮停止', 'ws-http-a'); const held = await barrier(c);
      try { await pageFor(stopped, async (page) => {
        await waitText(page, '停止前草稿'); const response = page.waitForResponse((res) => res.url().endsWith(`/runs/${active.run_id}/cancel`) && res.request().method() === 'POST');
        await page.getByRole('button', { name: '停止', exact: true }).click(); assert.equal((await (await response).json()).status, 'cancelling');
      }); } finally { await release(c, held); }
      assert.equal((await done(c, active.run_id)).status, 'cancelled');
      await scenario(c, { chunks: ['重试后的完整回答'] });
      await pageFor(stopped, async (page) => { await page.getByRole('button', { name: '重试', exact: true }).waitFor(); await page.locator('.workspace-controls select').nth(1).selectOption('mock-small:1'); await page.getByRole('button', { name: '重试', exact: true }).click(); const retried = await until(() => pageRunId(page), (rid) => rid !== active.run_id, '按钮重试新Run'); const result = await done(c, retried); assert.equal(result.parent_run_id, active.run_id); assert.equal(result.model.profile_id, 'mock-small'); });
      const failed = await fresh('UI_012-failed'); await scenario(c, { kind: 'http-error', http_status: 401 }); const failedSource = await send(c, failed, '失败按钮来源', 'ws-http-a'); assert.equal((await done(c, failedSource.run_id)).status, 'failed'); await scenario(c);
      await pageFor(failed, async (page) => { assert.equal(await page.getByRole('button', { name: '重新生成', exact: true }).count(), 0); await page.getByRole('button', { name: '重试', exact: true }).click(); const retry = await until(() => pageRunId(page), (rid) => rid !== failedSource.run_id, 'failed重试'); assert.equal((await done(c, retry)).model.profile_id, 'ws-http-a'); });
      await request(c, `/api/v2/threads/${t.thread_id}`, { method: 'PATCH', body: { archived: true } });
      await pageFor(t, async (page) => { assert.equal(await page.getByRole('button', { name: '重新生成', exact: true }).count(), 0); assert.equal(await page.getByRole('button', { name: '重试', exact: true }).count(), 0); assert.equal(await page.locator('textarea').isDisabled(), true); });
      return { actual: 'succeeded/failed/cancelled/running四来源按钮实际执行；响应挂起时pending禁用阻止重复操作，默认沿源模型/手动切换生效；停止先cancelling，归档隐藏关联写动作。', source_run_id: source.run_id, target_run_id: target };
    });
    // UI_013：从真实持久消息分支，刷新后仍保留选中子路径。
    await suite.test('UI_013', async () => {
      const t = await fresh('UI_013'); await answer(c, t, '共同祖先'); for (let i = 0; i < 25; i++) await answer(c, t, `父分支未来后缀${i}`);
      await pageFor(t, async (page) => {
        await page.getByRole('button', { name: '加载更早消息', exact: true }).waitFor(); await page.getByRole('button', { name: '加载更早消息', exact: true }).click();
        await waitText(page, '共同祖先'); assert.equal(await page.locator('.message').count(), 52); await page.locator('.message.user').filter({ hasText: '共同祖先' }).getByRole('button', { name: '从此处分支' }).click();
        await until(() => page.locator('.message-list').innerText(), (value) => value.includes('共同祖先') && !value.includes('父分支未来后缀'), '子路径隔离');
        const selector = page.locator('.workspace-controls select').first(); const child = await selector.inputValue(); assert.notEqual(child, t.default_branch_id);
        await selector.selectOption(t.default_branch_id); await waitText(page, '父分支未来后缀'); await selector.selectOption(child);
        await until(() => page.locator('.message-list').innerText(), (value) => value.includes('共同祖先') && !value.includes('父分支未来后缀'), '父子选择器切回子路径');
        await page.reload(); await waitTitle(page, t.title); assert.ok(!(await page.locator('.message-list').innerText()).includes('父分支未来后缀'));
      });
      return { actual: '真实页面以持久用户消息分叉，共同祖先只呈现一次，父未来后缀未进入子路径；刷新恢复所选分支。' };
    });
    // UI_014：服务端已接受、浏览器响应丢失，恢复入口必须沿用原键/原正文。
    await suite.test('UI_014', async () => {
      const t = await fresh('UI_014'); const payloads = []; let accepted;
      await pageFor(t, async (page) => {
        let first = true;
        await page.route(`**/api/v2/threads/${t.thread_id}/messages`, async (route) => {
          payloads.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() });
          const response = await route.fetch(); accepted = await response.json();
          if (first) { first = false; await route.abort('connectionfailed'); } else await route.fulfill({ response });
        });
        await page.locator('textarea').fill('未知结果的原正文'); await page.getByRole('button', { name: '发送', exact: true }).click();
        await page.getByRole('button', { name: '重试原提交', exact: true }).waitFor(); await page.locator('textarea').fill('后来编辑的不同正文');
        await page.getByRole('button', { name: '重试原提交', exact: true }).click(); await waitText(page, '未知结果的原正文');
      });
      assert.equal(payloads.length, 2); assert.deepEqual(payloads[0], payloads[1]); await done(c, accepted.run_id);
      assert.equal((await detail(c, t.thread_id)).messages.filter((item) => item.role === 'user').length, 1);
      const related = [];
      for (const kind of ['retry', 'regenerate']) {
        const own = await fresh(`UI_014-${kind}`); const source = kind === 'retry' ? await cancelledSource(c, own, `关联操作${kind}`) : await answer(c, own, `关联操作${kind}`);
        const requests = []; let target; await pageFor(own, async (page) => {
          let first = true; await page.route(`**/api/v2/runs/${source.run_id}/${kind}`, async (route) => {
            requests.push({ key: route.request().headers()['idempotency-key'], body: route.request().postDataJSON() }); const response = await route.fetch(); target = await response.json();
            if (first) { first = false; await route.abort('connectionfailed'); } else await route.fulfill({ response });
          });
          await page.getByRole('button', { name: kind === 'retry' ? '重试' : '重新生成', exact: true }).waitFor(); await page.getByRole('button', { name: kind === 'retry' ? '重试' : '重新生成', exact: true }).click();
          await page.getByRole('button', { name: '重试原操作', exact: true }).waitFor(); await page.locator('.workspace-controls select').nth(1).selectOption('mock-small:1');
          await page.getByRole('button', { name: '重试原操作', exact: true }).click(); await until(() => pageRunId(page), (rid) => rid === target.run_id, '关联操作原身份恢复');
        });
        assert.equal(requests.length, 2); assert.deepEqual(requests[0], requests[1]); await done(c, target.run_id); related.push({ kind, source: source.run_id, target: target.run_id });
      }
      return { actual: 'message及retry/regenerate三类已接受响应丢失后均重放原键/规范请求；编辑正文或改模型不替换原操作，不重复创建业务身份。', run_id: accepted.run_id, related };
    });
    // UI_015 / TP-THR-09：真实服务端归档事实投影到两个互斥列表，不能只改徽标。
    await suite.test('UI_015', async () => {
      const normal = await fresh('UI_015普通'); const archived = await fresh('UI_015归档');
      await request(c, `/api/v2/threads/${archived.thread_id}`, { method: 'PATCH', body: { archived: true } });
      await pageFor(normal, async (page) => {
        const item = (title) => page.locator('.thread-item').filter({ hasText: title });
        assert.equal(await page.getByRole('button', { name: '普通会话', exact: true }).getAttribute('aria-pressed'), 'true');
        assert.equal(await item(normal.title).count(), 1); assert.equal(await item(archived.title).count(), 0);
        // 审批补充：切视图会推进epoch，真实失败必须可见而非被旧epoch吞掉。
        const detailPattern = '**/api/v2/threads/*';
        await page.route(detailPattern, route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'DATABASE_UNAVAILABLE', message: '测试注入的读取故障' }) }));
        try {
          await page.getByRole('button', { name: '已归档', exact: true }).click();
          await until(() => page.locator('.error-banner').textContent(), value => value.includes('DATABASE_UNAVAILABLE'), '视图读取错误可见');
          assert.equal(await page.locator('textarea').isDisabled(), true);
        } finally { await page.unroute(detailPattern); }
        await page.getByRole('button', { name: '普通会话', exact: true }).click(); await waitTitle(page, normal.title);
        await page.getByRole('button', { name: '已归档', exact: true }).click();
        await until(() => item(archived.title).count(), count => count === 1, '归档列表出现目标');
        assert.equal(await item(normal.title).count(), 0); await selectThread(page, archived);
        assert.equal(await page.locator('textarea').isDisabled(), true);
        await page.getByRole('button', { name: '取消归档', exact: true }).click();
        await until(() => page.getByRole('button', { name: '普通会话', exact: true }).getAttribute('aria-pressed'), value => value === 'true', '取消归档回普通');
        await waitTitle(page, archived.title); assert.equal(await page.locator('textarea').isEnabled(), true);
        await page.getByRole('button', { name: '已归档', exact: true }).click(); assert.equal(await item(archived.title).count(), 0);
      });
      return { actual: '普通/已归档视图按服务端事实互斥显示；切视图读取503明确显示且可恢复，归档可读禁写，取消归档移动回普通且当前身份不变。', normal_thread_id: normal.thread_id, archived_thread_id: archived.thread_id };
    });
    // UI_016 / TP-THR-10：真实分页空视图与迟到响应；仅延迟真实HTTP，不伪造产品数据。
    await suite.test('UI_016', async () => {
      const archived = await fresh('UI_016旧归档'); await request(c, `/api/v2/threads/${archived.thread_id}`, { method: 'PATCH', body: { archived: true } });
      for (let i = 0; i < 101; i++) await fresh(`UI_016普通${i}`);
      await pageFor(null, async (page) => {
        await until(() => page.locator('.thread-item').count(), count => count === 100, '首屏100条摘要');
        await page.getByRole('button', { name: '已归档', exact: true }).click();
        assert.equal(await page.locator('.thread-item').count(), 0); assert.equal(await page.locator('textarea').isDisabled(), true);
        assert.ok((await page.locator('.thread-panel').innerText()).includes('已加载会话中暂无归档项，可加载更多'));
        let releasePage; const gate = new Promise(resolve => { releasePage = resolve; }); let received = false; let handled;
        const handledPage = new Promise(resolve => { handled = resolve; });
        const pattern = '**/api/v2/threads?*';
        await page.route(pattern, async route => {
          if (!new URL(route.request().url()).searchParams.has('cursor')) return route.continue();
          try { const response = await route.fetch(); received = true; await gate; await route.fulfill({ response }); } finally { handled(); }
        });
        try {
          await page.getByRole('button', { name: '加载更多', exact: true }).click(); await until(() => received, Boolean, '真实分页已响应但挂起');
          await page.getByRole('button', { name: '普通会话', exact: true }).click(); releasePage(); await handledPage;
          await until(() => page.getByRole('button', { name: '加载更多', exact: true }).isEnabled(), Boolean, '旧分页退出');
          assert.equal(await page.locator('.thread-item small').count(), 0);
          await page.unroute(pattern); await page.getByRole('button', { name: '已归档', exact: true }).click();
          assert.equal(await page.locator('.thread-item').filter({ hasText: archived.title }).count(), 0, '迟到分页不得写入缓存');
          await page.getByRole('button', { name: '加载更多', exact: true }).click();
          await until(() => page.locator('.thread-item').filter({ hasText: archived.title }).count(), count => count === 1, '新分页读取首屏外归档');
          const titles = await page.locator('.thread-item').allTextContents(); assert.equal(new Set(titles).size, titles.length);
          assert.ok(titles.every(title => title.includes('已归档')));
        } finally { releasePage(); if (received) await handledPage; await page.unroute(pattern); }
      });
      return { actual: '100条普通项首屏不误报无归档，空视图禁写且可加载更多；切视图丢弃真实迟到分页，原游标可重试，加载后归档列表不混入普通项且无重复。', archived_thread_id: archived.thread_id };
    });
    // UI_017 / TP-THR-11：首屏之外的有效归档身份需独立校验和恢复，不能默认跳到普通。
    await suite.test('UI_017', async () => {
      const t = await fresh('UI_017首屏外归档'); const created = await answer(c, t, 'UI_017持久历史');
      const before = await detail(c, t.thread_id); await request(c, `/api/v2/threads/${t.thread_id}`, { method: 'PATCH', body: { archived: true } });
      for (let i = 0; i < 101; i++) await fresh(`UI_017普通${i}`);
      const first = (await request(c, '/api/v2/threads?include_archived=true&limit=100')).data;
      assert.ok(!first.threads.some(item => item.thread_id === t.thread_id));
      await pageFor(t, async page => {
        assert.equal(await page.getByRole('button', { name: '已归档', exact: true }).getAttribute('aria-pressed'), 'true');
        await waitText(page, 'UI_017持久历史'); assert.equal(await page.locator('textarea').isDisabled(), true);
        assert.equal(await pageRunId(page), created.run_id); await page.reload(); await waitTitle(page, t.title); await waitText(page, 'UI_017持久历史');
        assert.equal(await page.getByRole('button', { name: '已归档', exact: true }).getAttribute('aria-pressed'), 'true');
      });
      assert.deepEqual((await detail(c, t.thread_id)).messages, before.messages);
      return { actual: '有效归档偏好不在首屏时经服务端独立读取，自动进入归档只读视图；刷新恢复同Thread/Branch/Run和完整历史，事实不变。', thread_id: t.thread_id, run_id: created.run_id };
    });
    // UI_018 / TP-THR-12：归档视图中的新建入口必须展示并选中新普通会话。
    await suite.test('UI_018', async () => {
      const t = await fresh('UI_018归档来源'); await request(c, `/api/v2/threads/${t.thread_id}`, { method: 'PATCH', body: { archived: true } });
      let created;
      await pageFor(t, async page => {
        const accepted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/threads' && response.request().method() === 'POST');
        await page.getByRole('button', { name: '新建会话', exact: true }).click(); created = await (await accepted).json();
        await waitTitle(page, created.title); await until(() => page.locator('textarea').isEnabled(), Boolean, '新会话可写');
        assert.equal(await page.getByRole('button', { name: '普通会话', exact: true }).getAttribute('aria-pressed'), 'true');
        assert.equal(await page.locator('.thread-item.active').count(), 1);
        assert.equal(await page.evaluate(() => localStorage.getItem('sesrag.selectedThreadId')), created.thread_id);
        assert.equal(await page.locator('.thread-item').filter({ hasText: t.title }).count(), 0);
      });
      assert.notEqual(created.thread_id, t.thread_id); assert.equal(created.archived_at, null);
      assert.ok((await detail(c, t.thread_id)).thread.archived_at);
      return { actual: '归档视图点击新建后回普通视图，选中新Thread/默认Branch且输入可用，来源归档事实不变。', source_thread_id: t.thread_id, new_thread_id: created.thread_id };
    });
  } finally { await browser.close(); }
  return suite.finish();
}
main(process.argv[process.argv.indexOf('--context') + 1]).then((code) => { process.exitCode = code; }).catch((error) => { console.error(`【workspace】工程错误：${error.message}`); process.exitCode = 2; });
