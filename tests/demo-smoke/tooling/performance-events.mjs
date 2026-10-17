import os from 'node:os'
import { assert, poll } from '../lib/category-kit.mjs'
import { stoppedWorker, readSSE } from '../specific_test_script/run-test-driver.mjs'
import { frontendResource } from './frontend-resources.mjs'

function calibrate(ctx) {
  const samples = []
  for (let i = 0; i < 3; i++) {
    const hostBefore = Date.now()
    const container = ctx.python("import json,time\nprint('SMOKE_JSON:'+json.dumps({'utc_ms':time.time_ns()/1000000}))", { service: 'worker' })
    const hostAfter = Date.now()
    const apiBefore=Date.now(), api=ctx.python("import json,time\nprint('SMOKE_JSON:'+json.dumps({'utc_ms':time.time_ns()/1000000}))"), apiAfter=Date.now()
    const dbBefore = Date.now(), db = ctx.sql('SELECT extract(epoch FROM clock_timestamp())*1000 AS utc_ms')[0], dbAfter = Date.now()
    samples.push({ host_before: hostBefore, host_after: hostAfter, container_utc: container.utc_ms,
      container_offset: [container.utc_ms-hostAfter-1,container.utc_ms-hostBefore+1], api_offset:[api.utc_ms-apiAfter-1,api.utc_ms-apiBefore+1],api_utc:api.utc_ms,api_before:apiBefore,api_after:apiAfter,
      db_before: dbBefore, db_after: dbAfter, db_utc: Number(db.utc_ms), db_offset: [Number(db.utc_ms)-dbAfter-1,Number(db.utc_ms)-dbBefore+1] })
  }
  return { samples, container_offset: [Math.max(...samples.map(x=>x.container_offset[0])),Math.min(...samples.map(x=>x.container_offset[1]))],
    db_offset: [Math.max(...samples.map(x=>x.db_offset[0])),Math.min(...samples.map(x=>x.db_offset[1]))] }
}

export async function eventPerformance(ctx) {
  const before = calibrate(ctx), samples = [], warm = []
  const thread = await ctx.thread('PERF002真实订阅屏障')
  for (let i = 0; i < 23; i++) {
    const row = await stoppedWorker(ctx, async () => {
      const run = await ctx.submit(thread.thread_id,'执行首事件性能样本')
      const resource=frontendResource(ctx,'perf-sse',{run_id:run.run_id});resource.running()
      let initial, started, released = false
      const stream = readSSE(ctx,run.run_id,{timeoutMs:20000,onFrame: frame => {
        const observed = { event: frame.data, client_utc_ms: Date.now(), client_monotonic_ms: performance.now() }
        if (frame.data.type === 'run.created') initial = observed
        if (frame.data.type === 'run.started') { assert.ok(released); started = observed }
      }})
      try {
        await poll(()=>initial,5000,'订阅未收到创建事实，不能放行Worker')
        assert.equal((await ctx.run(run.run_id)).status,'queued')
        released = true
        assert.equal(ctx.compose(['start','worker']).code,0)
        const result = await stream
        assert.ok(result.eof && !result.timed_out && !result.stream_error); assert.ok(started)
        const persisted = (await ctx.events(run.run_id)).find(e=>e.type==='run.started')
        assert.equal(started.event.event_id,persisted.event_id); assert.equal(Date.parse(started.event.occurred_at),Date.parse(persisted.occurred_at))
        assert.ok(initial.event.seq<persisted.seq)
        const wallClockDrift=Math.abs((started.client_utc_ms-initial.client_utc_ms)-(started.client_monotonic_ms-initial.client_monotonic_ms))
        if(wallClockDrift>5)throw Object.assign(new Error('宿主UTC与单调计时发生跳变，样本不能可靠比较'),{blocked:true})
        return { index:i,run_id:run.run_id,event_id:persisted.event_id,seq:persisted.seq,initial_before_release:true,host_wall_clock_drift_ms:wallClockDrift,
          occurred_at:persisted.occurred_at,client_utc_ms:started.client_utc_ms,raw_ms:started.client_utc_ms-Date.parse(persisted.occurred_at) }
      } finally { await stream;resource.closed({observed_stream_finally:true}) }
    })
    ;(i<3?warm:samples).push(row)
  }
  const after = calibrate(ctx)
  // 前后区间取外包络，显式包含漂移与毫秒取整误差；跨阈值只能blocked。
  const offsets=[Math.min(before.container_offset[0],after.container_offset[0]),Math.max(before.container_offset[1],after.container_offset[1])]
  for(const row of samples) row.interval_ms=[row.raw_ms+offsets[0],row.raw_ms+offsets[1]]
  const evidence={warm,samples,calibration:{before,after,offsets},environment:{host_utc:new Date().toISOString(),cpus:os.cpus().length,memory_gib:os.totalmem()/1024**3,load:os.loadavg(),mock:true,worker_count:1,sse_poll_seconds:ctx.python("import json\nfrom backend.config import Settings\nprint('SMOKE_JSON:'+json.dumps(Settings().sse_poll_interval))")}}
  ctx.evidence('perf/first-execution-event.json',evidence)
  assert.equal(samples.length,20);assert.equal(warm.length,3)
  assert.ok(samples.every(row=>row.interval_ms[0]<2000),'至少一个样本确定超出2秒')
  if(samples.some(row=>row.interval_ms[1]>=2000)||offsets[0]>offsets[1])throw Object.assign(new Error('时钟误差区间跨越2秒，不能确定性能通过'),{blocked:true})
  return { measured:20,warmup:3,max_upper_ms:Math.max(...samples.map(row=>row.interval_ms[1])),offsets }
}
