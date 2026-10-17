import { executionCoverage } from './execution-coverage.mjs';
import {runCategory,assert,poll} from '../lib/category-kit.mjs';
export const coveredCases=Array.from({length:25},(_,i)=>`WK_${String(i+1).padStart(3,'0')}`);

await runCategory('wk',async s=>{
 const c=s.ctx;
 // WK_001：通过生产应用写入queued，真实PG领取；不INSERT或手改租约。
 try {
  assert.equal(c.compose(['stop','worker']).code,0);
  await s.check('WK_001','TP-WK-003','claim','实际领取写leased、worker、generation/attempt各+1和有界租约',async()=>{
   const t=await c.thread('WK_001领取');const m=await c.submit(t.thread_id,'真实PG领取');const before=c.sql(`SELECT task_id,state,attempt,generation FROM tasks WHERE task_id='${m.task_id}'`)[0];
   const result=c.python(`import asyncio,json\nfrom datetime import datetime,timezone,timedelta\nfrom backend.config import Settings\nfrom backend.db.session import create_engine,create_session_factory\nfrom backend.infrastructure.queue.postgres_queue import claim_next_task\nasync def main():\n cfg=Settings();e=create_engine(cfg);f=create_session_factory(e)\n try:\n  async with f() as s:\n   before=datetime.now(timezone.utc);t=await claim_next_task(s,'wk-driver',cfg);after=datetime.now(timezone.utc)\n   result=None if t is None else {'task_id':t.task_id,'state':t.state,'worker_id':t.worker_id,'attempt':t.attempt,'generation':t.generation,'lease':t.lease_expires_at.isoformat(),'ttl_seconds':cfg.task_lease_ttl,'lease_in_server_bounds':before+timedelta(seconds=cfg.task_lease_ttl)<=t.lease_expires_at<=after+timedelta(seconds=cfg.task_lease_ttl)}\n  print('SMOKE_JSON:'+json.dumps(result))\n finally: await e.dispose()\nasyncio.run(main())`);
   assert.equal(result.task_id,m.task_id,'其它排队任务影响领取排序');assert.equal(result.state,'leased');assert.equal(result.worker_id,'wk-driver');assert.equal(result.attempt,before.attempt+1);assert.equal(result.generation,before.generation+1);assert.ok(result.lease_in_server_bounds,'实际租约必须位于同一服务端调用前后UTC+TTL的区间');
   await c.request(`/api/v1/runs/${m.run_id}/cancel`,{method:'POST'});return result;
  });
  await s.check('WK_001','TP-WK-002','queued-qualification','可用queued任务经真实claim领取',async()=>{const rows=c.sql("SELECT state,worker_id,generation,attempt FROM tasks WHERE worker_id='wk-driver'");assert.ok(rows.length>0);assert.ok(rows.every(x=>x.generation>=1&&x.attempt>=1));return rows;});
 }finally{c.compose(['start','worker']);await c.ready();}
 // WK_003：真实Runtime实例模拟相同PID，揭示默认身份碰撞，不把显式ID前提当修复。
 await s.check('WK_003','TP-WK-005','default-identity','同进程身份稳定，默认不同实例不因PID相同而撞ID',()=>{
  const r=c.python(`import os,json\nfrom unittest.mock import patch\nfrom backend.config import Settings\nfrom backend.workers.runtime import WorkerRuntime\nfrom backend.infrastructure.events.redis_notifier import RedisNotifier\nwith patch.dict(os.environ,{},clear=True),patch('os.getpid',return_value=1):\n a=WorkerRuntime(Settings(),None,RedisNotifier(Settings()));b=WorkerRuntime(Settings(),None,RedisNotifier(Settings()))\n result={'a':a.worker_id,'b':b.worker_id,'stable':a.worker_id==a.worker_id}\nprint('SMOKE_JSON:'+json.dumps(result))`);
  c.evidence('wk/default-identity.json',r);assert.ok(r.stable);assert.notEqual(r.a,r.b,'两个同PID实例默认worker_id碰撞，显式测试ID并未修复默认生成');return r;
 });
 await s.check('WK_013','TP-WK-016','backoff-values','base2的attempt1/2/3真实函数返回2/4/8',()=>{const r=c.python(`import json\nfrom backend.infrastructure.queue.postgres_queue import retry_delay_seconds\nprint('SMOKE_JSON:'+json.dumps([retry_delay_seconds(x,2) for x in [1,2,3]]))`);assert.deepEqual(r,[2,4,8]);return r;});
 // WK_016：短deadline经生产应用创建，等待真实时间，不能手改deadline/state。
 try {
  assert.equal(c.compose(['stop','worker']).code,0);
  let task;
  await s.check('WK_016','TP-WK-020','expired-queued','超过真实deadline的queued Task/Run显式failed且TASK_DEADLINE_EXCEEDED',async()=>{
   task=c.python(`import asyncio,json\nfrom backend.config import Settings\nfrom backend.db.session import create_engine,create_session_factory\nfrom backend.application.threads import create_thread,create_message_run\nasync def main():\n cfg=Settings(task_deadline=1);e=create_engine(cfg);f=create_session_factory(e)\n try:\n  async with f() as s:\n   t=await create_thread(s,cfg,'WK_016截止');m,r,k,d=await create_message_run(s,cfg,t.thread_id,'截止测试',None)\n   print('SMOKE_JSON:'+json.dumps({'thread_id':t.thread_id,'run_id':r.run_id,'task_id':k.task_id,'deadline':k.deadline_at.isoformat()}))\n finally: await e.dispose()\nasyncio.run(main())`);
   await poll(()=>Date.now()>Date.parse(task.deadline)+200,4000);
   c.compose(['start','worker']);await c.ready();
   let final;try {final=await poll(async()=>{const r=await c.run(task.run_id);return r.status==='failed'?r:null;},4000,'截止后仍未结算failed');}catch(error){c.evidence('wk/deadline-observed.json',{...task,observed:await c.run(task.run_id)});throw error;}
   assert.equal(final.task.state,'failed');assert.equal(final.last_error_code,'TASK_DEADLINE_EXCEEDED');return final;
  });
 }finally {c.compose(['start','worker']);await c.ready();}
 // WK_022：停机期间新建两个各自独立Run，重启只继续原身份。
 await s.check('WK_022','TP-WK-026','queued-restart','正常Worker重启继续原Task/Run且用户/assistant各唯一',async()=>{
  const runs=[];try {assert.equal(c.compose(['stop','worker']).code,0);for(let i=0;i<2;i++){const t=await c.thread(`WK_022-${i}`);const r=await c.submit(t.thread_id,'停机排队');assert.equal((await c.run(r.run_id)).status,'queued');runs.push({t,r});}}finally{c.compose(['start','worker']);await c.ready();}
  const facts=[];for(const {t,r}of runs){const terminal=await c.waitRun(r.run_id);assert.equal(terminal.status,'succeeded');assert.equal(terminal.task.task_id,r.task_id);const detail=await c.detail(t.thread_id);assert.equal(detail.runs.length,1);assert.equal(detail.messages.filter(x=>x.role==='user').length,1);assert.equal(detail.messages.filter(x=>x.role==='assistant').length,1);facts.push({thread_id:t.thread_id,...r,status:terminal.status});}return facts;
 });
 await s.check('WK_024','TP-WK-029','claim-log','默认实际claim日志含task/run/worker/generation，不只存在logger.extra',async()=>{
  const t=await c.thread('WK_024日志');const r=await c.submit(t.thread_id,'关联日志');const terminal=await c.waitRun(r.run_id);const logs=c.compose(['logs','--no-color','--tail','500','worker']);c.evidence('wk/claim-logs.log',logs.stdout);const line=logs.stdout.split(/\r?\n/).find(x=>/task claimed/.test(x)&&x.includes(r.task_id));assert.ok(line&&line.includes(r.run_id),'默认claim行未输出task_id/run_id等关联字段');assert.ok(line.includes(c.context.compose_project+'-worker'));assert.ok(new RegExp(`generation["' :=]+${terminal.task.generation}`).test(line),'claim行缺generation');return {task_id:r.task_id,run_id:r.run_id,generation:terminal.task.generation,log:'claim关联字段齐全'};
 });
 await s.check('WK_024','TP-WK-029','success-log','真实成功动作日志含task/run/worker/generation',async()=>{const t=await c.thread('WK_024成功日志');const r=await c.submit(t.thread_id,'成功动作日志');const terminal=await c.waitRun(r.run_id);const logs=c.compose(['logs','--no-color','--tail','500','worker']);c.evidence('wk/success-logs.log',logs.stdout);const line=logs.stdout.split(/\r?\n/).find(x=>/succeed|success|成功/.test(x)&&x.includes(r.task_id));assert.ok(line&&line.includes(r.run_id),'实际success动作缺关联日志');assert.ok(line.includes(c.context.compose_project+'-worker'));assert.ok(new RegExp(`generation["' :=]+${terminal.task.generation}`).test(line));return {task_id:r.task_id,run_id:r.run_id,success_log:true};});
  await executionCoverage(s);
});
