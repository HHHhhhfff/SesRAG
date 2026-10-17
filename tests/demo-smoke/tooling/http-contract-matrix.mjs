import fs from 'node:fs'
import path from 'node:path'
import { assert, execute, repoRoot } from '../lib/category-kit.mjs'
import { contractValidator, validateContract } from '../lib/api-contracts.mjs'
import { stoppedWorker, readSSE } from '../specific_test_script/run-test-driver.mjs'
import { pgScenario } from './pg-execution.mjs'

// 实际HTTP响应先验证原始字段/敏感哨兵，再写脱敏证据；不使用OpenAPI文件存在代验。
export async function httpContractMatrix(ctx) {
  const ajv = contractValidator(), rows = []
  const api = name => 'api_responses_v1.json#/$defs/' + name
  const check = (route, method, status, schema, response) => {
    assert.equal(response.status, status, `${method} ${route}`)
    validateContract(ajv, schema, response.body)
    assert.ok(!JSON.stringify(response.body).includes('PRIVATE_CONTRACT_SENTINEL'))
    rows.push({ route, method, status, schema }); return response.body
  }
  const call = async (route, method, status, schema, body, headers) => check(route, method, status, schema, await ctx.request(route, { method, body, headers }))
  const thread = await call('/api/v1/threads','POST',201,'thread_v1.json',{title:'QLT完整契约'})
  await call('/api/v1/threads','GET',200,api('ThreadList'))
  let run
  await stoppedWorker(ctx, async () => {
    const route = `/api/v1/threads/${thread.thread_id}/messages`
    run = await call(route,'POST',201,api('MessageRunResponse'),{content:'契约原始输入'},{'Idempotency-Key':'contract-unique'})
    await call(route,'POST',200,api('MessageRunResponse'),{content:'契约原始输入'},{'Idempotency-Key':'contract-unique'})
    const cancelled = await ctx.submit(thread.thread_id,'取消契约')
    await call(`/api/v1/runs/${cancelled.run_id}/cancel`,'POST',200,api('CancelResponse'))
    const events = await call(`/api/v1/runs/${cancelled.run_id}/events`,'GET',200,api('EventListResponse'))
    assert.ok(events.events.some(event => event.type === 'run.cancelled'))
  })
  await ctx.waitRun(run.run_id)
  await call(`/api/v1/threads/${thread.thread_id}`,'GET',200,api('ThreadDetail'))
  await call(`/api/v1/runs/${run.run_id}`,'GET',200,'run_v1.json')
  await call(`/api/v1/runs/${run.run_id}/events`,'GET',200,api('EventListResponse'))
  const stream = await readSSE(ctx,run.run_id)
  assert.equal(stream.status,200); assert.ok(stream.eof)
  for (const frame of stream.frames) validateContract(ajv,'run_event_v1.json',frame.data)
  rows.push({route:'/api/v1/runs/{run_id}/events/stream',method:'GET',status:200,schema:'run_event_v1.json',frames:stream.frames.length})
  const document = check('/api/v1/documents','POST',201,'document_v1.json',await ctx.upload('contract.txt',Buffer.from('安全契约引用')))
  await ctx.waitDoc(document.document_id)
  await call('/api/v1/documents','GET',200,api('DocumentListResponse'))
  await call(`/api/v1/documents/${document.document_id}/index`,'POST',200,api('IndexResponse'))
  await call(`/api/v1/threads/${thread.thread_id}/archive`,'POST',200,api('ArchiveResponse'))
  // Demo归档仅元数据，不承诺禁止继续发问。
  const archivedRun = await call(`/api/v1/threads/${thread.thread_id}/messages`,'POST',201,api('MessageRunResponse'),{content:'归档后契约'})
  await ctx.waitRun(archivedRun.run_id)
  for (const [route,method,body] of [
    ['/api/v1/threads/missing','GET'],['/api/v1/threads/missing/archive','POST'],['/api/v1/threads/missing/messages','POST',{content:'合法请求'}],
    ['/api/v1/runs/missing','GET'],['/api/v1/runs/missing/cancel','POST'],['/api/v1/runs/missing/events','GET'],['/api/v1/runs/missing/events/stream','GET'],['/api/v1/documents/missing/index','POST'],
  ]) await call(route,method,404,api('ErrorResponse'),body)
  for (const [route,method,body] of [
    ['/api/v1/threads','POST',{title:'PRIVATE_CONTRACT_SENTINEL'.repeat(30)}],['/api/v1/threads','POST',{title:{PRIVATE_CONTRACT_SENTINEL:'secret'}}],
    ['/api/v1/threads','POST',['PRIVATE_CONTRACT_SENTINEL']],['/api/v1/threads/id/messages','POST',{content:['PRIVATE_CONTRACT_SENTINEL']}],
    ['/api/v1/threads/id/messages','POST',{content:''}],['/api/v1/runs/id/events?after_seq=PRIVATE_CONTRACT_SENTINEL','GET'],['/api/v1/runs/id/events?after_seq=-1','GET'],['/api/v1/documents','POST',new FormData()],
  ]) await call(route,method,422,api('ValidationErrorResponse'),body)
  const malformed = await fetch(ctx.args.BaseUrl+'/api/v1/threads',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"PRIVATE_CONTRACT_SENTINEL":,}',signal:AbortSignal.timeout(10000)})
  check('/api/v1/threads malformed JSON','POST',422,api('ValidationErrorResponse'),{status:malformed.status,body:await malformed.json()})
  for (const [name, bytes, mime, status] of [
    ['invalid:name.txt',Buffer.from('text'),'text/plain',422],['wrong.exe',Buffer.from('text'),'application/octet-stream',415],
    ['wrong.txt',Buffer.from('text'),'image/png',415],['large.txt',Buffer.alloc(10*1024*1024+1,97),'text/plain',413],
  ]) check('/api/v1/documents '+name,'POST',status,api('ErrorResponse'),await ctx.upload(name,bytes,mime))
  await call('/health/live','GET',200,api('HealthLive'))
  await call('/health/ready','GET',200,'health_v1.json')
  const eventStates = await pgScenario(ctx,'event-contracts')
  for(const state of ['retry','failed']) {
    for(const event of eventStates.trace[state]) validateContract(ajv,'run_event_v1.json',event)
    validateContract(ajv,'run_v1.json',eventStates.trace[state+'_detail'])
    rows.push({route:'/api/v1/runs/{run_id}/events',method:'GET',status:200,schema:'run_event_v1.json',state})
  }
  // 本run专属PG停止制造真实503；finally恢复，其他分类顺序执行。
  try {
    assert.equal(ctx.compose(['stop','-t','2','postgres']).code,0)
    await call('/health/ready','GET',503,'health_v1.json')
    for (const [route,method,body] of [
      ['/api/v1/threads','GET'],['/api/v1/threads','POST',{title:'故障'}],['/api/v1/threads/id','GET'],['/api/v1/threads/id/archive','POST'],
      ['/api/v1/threads/id/messages','POST',{content:'故障'}],['/api/v1/runs/id','GET'],['/api/v1/runs/id/events','GET'],['/api/v1/runs/id/events/stream','GET'],['/api/v1/runs/id/cancel','POST'],['/api/v1/documents','GET'],['/api/v1/documents/id/index','POST'],
    ]) await call(route,method,503,api('ErrorResponse'),body)
    check('/api/v1/documents','POST',503,api('ErrorResponse'),await ctx.upload('db-failure.txt',Buffer.from('安全故障上传')))
  } finally { assert.equal(ctx.compose(['start','postgres']).code,0); await ctx.ready(30000) }
  // 生成到本run tmp再逐字diff；生成器不覆盖正式api.ts以制造通过。
  const temporary = path.join(path.dirname(ctx.args.FixtureDir),'contract-types.generated.ts')
  try {
    const result = execute(process.execPath,[path.join(repoRoot,'frontend/scripts/generate-api-types.mjs'),'--output',temporary])
    assert.equal(result.code,0)
    assert.equal(fs.readFileSync(temporary,'utf8'),fs.readFileSync(path.join(repoRoot,'frontend/src/types/api.ts'),'utf8'),'前端类型与契约漂移')
  } finally { if(fs.existsSync(temporary))fs.unlinkSync(temporary) }
  ctx.evidence('qlt/http-contract-matrix.json',{rows,type_generation_tmp_diff:true})
  return {responses:rows.length,raw_validation_sentinels_absent:true,type_generation_tmp_diff:true}
}
