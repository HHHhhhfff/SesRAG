import crypto from 'node:crypto';
import { assert, key, thread, answer, detail, request, scenario, observations } from './support.mjs';
import { upload } from './compatibility-runtime.mjs';
const hash = (text) => crypto.createHash('sha256').update(text).digest('hex');

export const contextRuntime = {
  // CTX_001：安全hash与角色序列来自受控HTTP真正收到的请求，不预拼Prompt。
  async CTX_001({ context: c }) {
    const t = await thread(c, `CTX_001-${key().slice(0, 8)}`); await scenario(c, { chunks: ['HISTORY-ASSISTANT-OLD'] });
    const first = await answer(c, t, 'HISTORY-USER-OLD', 'ws-http-a'); const second = await answer(c, t, 'HISTORY-USER-NEW', 'ws-http-a');
    const observed = await observations(c); assert.equal(observed.truncated, false);
    const received = observed.requests.filter((item) => item.path.endsWith('/chat/completions')).at(-1);
    assert.deepEqual(received.message_summaries.slice(-3).map((item) => ({ role: item.role, sha256: item.sha256 })),
      [{ role: 'user', sha256: hash('HISTORY-USER-OLD') }, { role: 'assistant', sha256: hash('HISTORY-ASSISTANT-OLD') }, { role: 'user', sha256: hash('HISTORY-USER-NEW') }]);
    const plan = (await request(c, `/api/v2/runs/${second.run_id}/context`)).data.plan;
    assert.ok(plan.selected_message_ids.includes(first.message_id)); assert.equal(plan.anchor_message_id, second.message_id);
    return { actual: '第二轮实际HTTP请求末三条依次为旧用户/旧assistant/当前用户，角色与原文hash一一对应，锚点和选中Message身份正确。', run_id: second.run_id, request: received, context_plan: plan };
  },
  // CTX_011：真实PG vector索引路径与精确Port淘汰断言共同证明引用子集。
  async CTX_011({ context: c }) {
    const docs = [];
    for (let index = 0; index < 3; index++) docs.push(await upload(c, `CTX_011-${index}.txt`, `EVIDENCE-CONTEXT-${index} ` + `文档${index}的虚构资料。`.repeat(100)));
    const t = await thread(c, `CTX_011-${key().slice(0, 8)}`); const created = await answer(c, t, 'EVIDENCE-CONTEXT 资料引用', 'ws-http-b');
    const plan = (await request(c, `/api/v2/runs/${created.run_id}/context`)).data.plan; const page = await detail(c, t.thread_id); const citations = page.messages.at(-1).citations;
    assert.ok(citations.length > 0 && plan.selected_evidence.length > 0);
    for (const citation of citations) {
      const selected = plan.selected_evidence.find((item) => item.document_id === citation.document_id && item.chunk_id === citation.chunk_id);
      assert.ok(selected); assert.equal(citation.index_batch_id, selected.index_batch_id); assert.deepEqual(citation.locations, selected.locations);
      assert.equal(citation.start_offset, selected.start_offset); assert.equal(citation.end_offset, selected.end_offset);
      assert.equal(docs.find((item) => item.document_id === citation.document_id).active_index_batch_id, citation.index_batch_id); assert.match(selected.content_hash, /^[a-f0-9]{64}$/);
    }
    assert.equal(citations.length, plan.selected_evidence.length);
    return { actual: '三个合成文档经正式上传/真实PG向量索引；最终每个引用均精确对应本Run选中Evidence的document/chunk/批次/位置/hash身份，不包含未选证据。', run_id: created.run_id, citations, selected_evidence: plan.selected_evidence };
  },
};
