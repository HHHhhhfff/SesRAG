import {runCategory,assert} from '../lib/category-kit.mjs';

export const coveredCases=['RAG_003'];

await runCategory('rag-empty',async s=>{
  const c=s.ctx;
  // RAG_003：runner专用全新数据库；先证明全库无active，不删除其他场景事实。
  await s.check('RAG_003','TP-RAG-004','formal-empty-run','独立空库正式Run成功，Journal检索count0/items空，最终回答明确无证据且无引用',async()=>{
    const initial=c.sql('SELECT (SELECT count(*) FROM documents) AS documents,(SELECT count(*) FROM chunks) AS chunks,(SELECT count(*) FROM threads) AS threads,(SELECT count(*) FROM runs) AS runs')[0];assert.deepEqual(initial,{documents:0,chunks:0,threads:0,runs:0});
    const thread=await c.thread('RAG_003独立空知识库会话'),submitted=await c.submit(thread.thread_id,'RAG_003当前知识库有什么安全资料？'),run=await c.waitRun(submitted.run_id,30000),events=await c.events(run.run_id),detail=await c.detail(thread.thread_id);
    assert.equal(run.status,'succeeded');assert.equal(run.task.state,'succeeded');assert.equal(run.last_error_code,null);assert.equal(run.task.last_error_code,null);const retrievals=events.filter(x=>x.type==='retrieval.completed');assert.equal(retrievals.length,1);const retrieval=retrievals[0];assert.equal(retrieval.data.count,0);assert.deepEqual(retrieval.data.items,[]);
    const deltas=events.filter(x=>x.type==='answer.delta').sort((a,b)=>a.seq-b.seq),assistants=detail.messages.filter(x=>x.role==='assistant'&&x.run_id===run.run_id);assert.equal(assistants.length,1);assert.ok(deltas.length);const assistant=assistants[0];assert.ok(assistant.content.includes('没有足够证据'));assert.equal(deltas.map(x=>x.data.text).join('').trim(),assistant.content);assert.deepEqual(assistant.citations,[]);assert.ok(deltas[0].seq>retrieval.seq);
    const completed=events.find(x=>x.type==='message.completed'),terminal=events.find(x=>x.type==='run.succeeded');assert.ok(completed&&terminal);assert.equal(completed.data.message_id,assistant.message_id);assert.deepEqual(completed.data.citations,[]);assert.equal(terminal.data.message_id,assistant.message_id);assert.ok(completed.seq>deltas.at(-1).seq&&terminal.seq>completed.seq);assert.ok(!events.some(x=>['run.failed','task.retry_scheduled'].includes(x.type)));
    const saved=c.sql(`SELECT r.status AS run_status,t.state AS task_state,m.content,m.citations_json FROM runs r JOIN tasks t ON t.task_id=r.primary_task_id JOIN messages m ON m.message_id=r.assistant_message_id WHERE r.run_id='${run.run_id}'`)[0];assert.equal(saved.run_status,'succeeded');assert.equal(saved.task_state,'succeeded');assert.equal(saved.content,assistant.content);assert.deepEqual(saved.citations_json,[]);assert.equal(c.sql('SELECT count(*) AS chunks FROM chunks')[0].chunks,0);
    return {thread_id:thread.thread_id,run_id:run.run_id,task_id:run.task.task_id,message_id:assistant.message_id,retrieval_count:0,citations:[],deltas:deltas.length,run_status:run.status,task_state:run.task.state,initial_empty:initial};
  });
});
