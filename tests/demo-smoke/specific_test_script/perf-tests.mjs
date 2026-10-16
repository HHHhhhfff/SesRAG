import {runCategory,assert} from '../lib/category-kit.mjs';
import os from 'node:os';
import {eventPerformance} from '../tooling/performance-events.mjs';
export const coveredCases=['PERF_001','PERF_002'];
await runCategory('perf',async s=>{
 // PERF_001：单调计时测量完整HTTP响应，不混预热，不从平均值推断SLO。
 await s.check('PERF_001','TP-PERF-001','20-samples','预热3次后20个独立消息201均在1秒内完整返回Run ID',async()=>{
  const c=s.ctx;const t=await c.thread('PERF_001消息提交');for(let i=0;i<3;i++){const r=await c.submit(t.thread_id,'预热问题',`warm-${i}`);await c.waitRun(r.run_id);}
  const samples=[];for(let i=0;i<20;i++){const start=performance.now();const r=await c.request(`/api/v1/threads/${t.thread_id}/messages`,{method:'POST',body:{content:`性能安全样本${i}`},headers:{'Idempotency-Key':`sample-${i}`}});const milliseconds=performance.now()-start;assert.equal(r.status,201);assert.ok(r.body.run_id);samples.push({index:i,ms:milliseconds,run_id:r.body.run_id,status:r.body.status});await c.waitRun(r.body.run_id);}
  const sorted=samples.map(x=>x.ms).sort((a,b)=>a-b);const stats={min:sorted[0],median:(sorted[9]+sorted[10])/2,p95:sorted[18],max:sorted[19],over_1000:samples.filter(x=>x.ms>=1000).length};const evidence={environment:{cpus:os.cpus().length,memory_gib:os.totalmem()/1024**3,platform:os.platform(),mock:true,worker_count:1,load:os.loadavg()},samples,stats};c.evidence('perf/message-latency.json',evidence);s.note(`PERF_001 最小${stats.min.toFixed(1)}ms/中位${stats.median.toFixed(1)}ms/p95 ${stats.p95.toFixed(1)}ms/最大${stats.max.toFixed(1)}ms/超标${stats.over_1000}`);assert.equal(stats.over_1000,0,'存在>=1秒样本');return evidence;
 });
 await s.check('PERF_002','TP-PERF-002','full-scenario','先收到初始事实再放行；3预热+20测量，run.started持久UTC到客户端到达含校准误差均小于2秒',()=>eventPerformance(s.ctx));
});
