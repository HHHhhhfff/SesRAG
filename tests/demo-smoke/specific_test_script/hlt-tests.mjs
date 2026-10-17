import { executionCoverage } from './execution-coverage.mjs';
import {runCategory,assert,poll} from '../lib/category-kit.mjs';
export const coveredCases=['HLT_001','HLT_002','HLT_003','HLT_004','HLT_005'];

await runCategory('hlt',async s=>{
 const c=s.ctx;
 // HLT_001/002：真实停止本次PG；所有分支结束恢复PG和Worker，错误互不短路。
 const t=await c.thread('HLT故障事实');const m=await c.submit(t.thread_id,'故障前事实');await c.waitRun(m.run_id);
 const countBefore=c.sql('SELECT count(*)::int AS count FROM threads')[0].count;
 await s.check('HLT_001','TP-HLT-001','normal','live正常返回200且只表示进程存活',async()=>{const r=await c.request('/health/live');assert.equal(r.status,200);assert.equal(r.body.status,'ok');return r;});
 try {
  assert.equal(c.compose(['stop','postgres']).code,0);
  await s.check('HLT_001','TP-HLT-001','pg-down','PG停机但API存活时live仍为200',async()=>{const r=await c.request('/health/live');assert.equal(r.status,200);assert.equal(r.body.status,'ok');return r;});
  await s.check('HLT_002','TP-HLT-002','ready','PG实际不可达时不声明database=ready',async()=>{const r=await c.request('/health/ready');c.evidence('hlt/pg-down-ready.json',r);assert.notEqual(r.body.database,'ready','ready固定宣告database=ready');return r;});
  for(const [sub,route,options] of [['create','/api/v1/threads',{method:'POST',body:{title:'不应创建'}}],['read',`/api/v1/threads/${t.thread_id}`,{}]])await s.check('HLT_002','TP-WK-027',sub,'PG中断业务返回安全稳定503且没有新事实',async()=>{const r=await c.request(route,options);c.evidence(`hlt/pg-down-${sub}.json`,r);assert.equal(r.status,503,`未映射依赖故障，实际HTTP ${r.status}`);assert.ok(r.body.code);return r;});
 } finally {assert.equal(c.compose(['start','postgres']).code,0);await poll(()=>{try{return c.sql('SELECT 1 AS alive')[0];}catch{return null;}},15000);c.compose(['start','worker']);await c.ready();}
 await s.check('HLT_002','TP-WK-027','no-phantom-facts','PG恢复后故障请求未创建幽灵Thread，原事实未丢',async()=>{assert.equal(c.sql('SELECT count(*)::int AS count FROM threads')[0].count,countBefore);assert.equal((await c.detail(t.thread_id)).thread.thread_id,t.thread_id);return {thread_count_unchanged:true,original_thread_id:t.thread_id};});
 // HLT_003：通知故障不能丢PG事实，ready真实性与业务/SSE分别判。
 let redisRunId,redisFacts;
 try {
  assert.equal(c.compose(['stop','redis']).code,0);
  await s.check('HLT_003','TP-HLT-003','ready','Redis运行中不可达时ready标degraded',async()=>{const r=await c.request('/health/ready');c.evidence('hlt/redis-down-ready.json',r);assert.equal(r.body.redis,'degraded','client非null导致假ready');return r;});
  let runId;
  await s.check('HLT_003','TP-HLT-006','facts','Redis中断下旧事实可读且新Run完成不换业务身份',async()=>{const old=await c.detail(t.thread_id);assert.ok(old.messages.length>=2);const thread=await c.thread('HLT_003通知降级');const run=await c.submit(thread.thread_id,'通知故障问题');runId=run.run_id;redisRunId=runId;const terminal=await c.waitRun(runId);assert.equal(terminal.status,'succeeded');redisFacts={detail:await c.detail(thread.thread_id),run:terminal,events:await c.events(runId),task:c.sql(`SELECT * FROM tasks WHERE task_id='${run.task_id}'`)};return {old_thread:t.thread_id,new_thread:thread.thread_id,run_id:runId,status:terminal.status};});
  await s.check('HLT_003','TP-SSE-005','redis-down-replay','Redis中断仍按PG完整补放到终态',async()=>{assert.ok(runId,'新Run前置失败');const response=await fetch(`${c.args.BaseUrl}/api/v1/runs/${runId}/events/stream`,{signal:AbortSignal.timeout(7000)});assert.equal(response.status,200);const text=await response.text();const ids=[...text.matchAll(/^id: (\d+)$/gm)].map(x=>Number(x[1]));assert.deepEqual(ids,(await c.events(runId)).map(x=>x.seq));assert.match(text,/event: run.succeeded/);return {run_id:runId,event_seqs:ids};});
 }finally {c.compose(['start','redis']);await c.ready();}
 await s.check('HLT_003','TP-HLT-006','redis-restart-compare','Redis重启后Thread/Message/Run/Task/Event身份与状态全部保持',async()=>{assert.ok(redisFacts,'Redis故障前置创建未成功');const after={detail:await c.detail(redisFacts.detail.thread.thread_id),run:await c.run(redisRunId),events:await c.events(redisRunId),task:c.sql(`SELECT * FROM tasks WHERE task_id='${redisFacts.run.task.task_id}'`)};assert.deepEqual(after,redisFacts);return {run_id:redisRunId,task_id:redisFacts.run.task.task_id,events:after.events.length,persistent_facts_unchanged:true};});
 // HLT_005：全部事实重启对比由本用例独立数据建立。
 await s.check('HLT_005','TP-HLT-005','restart','重启API不改变Thread/Message/Run/Task/Event/Document/Chunk',async()=>{
  const thread=await c.thread('HLT_005重启');const run=await c.submit(thread.thread_id,'重启恢复');await c.waitRun(run.run_id);const u=await c.upload('health-restart.md',Buffer.from('# 持久事实\n重启应保留'));assert.equal(u.status,201);await c.waitDoc(u.body.document_id);
  const snap=async()=>({detail:await c.detail(thread.thread_id),run:await c.run(run.run_id),tasks:c.sql(`SELECT * FROM tasks WHERE task_id='${run.task_id}' OR document_id='${u.body.document_id}' ORDER BY task_id`),events:await c.events(run.run_id),document:c.sql(`SELECT * FROM documents WHERE document_id='${u.body.document_id}'`),chunks:c.sql(`SELECT * FROM chunks WHERE document_id='${u.body.document_id}' ORDER BY seq`)});
  const before=await snap();assert.equal(c.compose(['restart','api']).code,0);await c.ready();assert.deepEqual(await snap(),before);return {thread_id:thread.thread_id,run_id:run.run_id,document_id:u.body.document_id,persistent:'全部不变'};
 });
  await executionCoverage(s);
});
