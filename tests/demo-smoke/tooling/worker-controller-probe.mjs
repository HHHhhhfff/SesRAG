import { Context, parseArgs, assert, execute, poll } from '../lib/category-kit.mjs';
import { startControlledWorker, closeResource, pgScenario } from './pg-execution.mjs';
import { assertMessageSource } from '../specific_test_script/run-test-driver.mjs';

// 长期控制入口真实正负哨兵：未启动即可清理、错误阶段拒绝、三片事实、main退出和容器关闭。
const ctx = new Context(parseArgs());
const empty = await startControlledWorker(ctx);
let intentionalFailureObserved = false;
try {
  assert.throws(() => closeResource(ctx, {...empty.resource, labels:{...empty.resource.labels,'sesrag.smoke.run_id':'wrong-run'}}));
  assert.equal((await empty.status()).controller_pid,empty.controllerPid);
  throw new Error('intentional-empty-body-failure');
} catch (error) {
  if (error.message !== 'intentional-empty-body-failure') throw error;
  intentionalFailureObserved = true;
} finally { await empty.close(); }
assert.ok(intentionalFailureObserved);
const emptyNames = execute('docker',['ps','-a','--filter',`name=^/${empty.resource.name}$`,'--format','{{.Names}}']);
assert.equal(emptyNames.code,0); assert.equal(emptyNames.stdout.trim(),'');
const fs = await import('node:fs');
const path = await import('node:path');
const registry = JSON.parse(fs.readFileSync(path.join(ctx.args.RuntimeDir,'execution-resources.json'),'utf8'));
assert.equal(registry.containers.find(item=>item.name===empty.resource.name).status,'closed');
ctx.evidence('execution/empty-body-failure-cleanup.json',{status:'passed',intentional_failure_observed:true,resource:empty.resource,container_absent:true,registry_closed:true});
await assert.rejects(() => pgScenario(ctx,'tool-negative-missing-scenario'));
const controller = await startControlledWorker(ctx);
const evidence = {base_url: controller.baseUrl, controller_pid: controller.controllerPid};
try {
  await assert.rejects(() => controller.start('invalid'));
  assert.equal((await controller.status()).worker_pid, null);
  const post = async (route, body) => {
    const response = await fetch(controller.baseUrl + route, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    assert.equal(response.status,201);return response.json();
  };
  const thread = await post('/api/v1/threads',{title:'控制器真实三片'});
  const run = await post(`/api/v1/threads/${thread.thread_id}/messages`,{content:'安全问题'});
  evidence.start = await controller.start('delta');
  evidence.reached = await controller.awaitReached();
  const facts = await controller.facts(run.run_id);
  assert.equal(facts.run.status,'running');
  assert.equal(facts.events.filter(e=>e.type==='answer.delta').length,1);
  await controller.release();
  evidence.final = await poll(async()=>{const f=await controller.facts(run.run_id);return f.run.status==='succeeded'?f:null;},10000);
  assert.equal(evidence.final.events.filter(e=>e.type==='answer.delta').length,3);
  const detail = await (await fetch(controller.baseUrl+'/api/v1/threads/'+thread.thread_id)).json();
  for(const message of detail.messages) {
    const persisted=evidence.final.messages.find(row=>row.message_id===message.message_id);
    assertMessageSource(message,persisted,message.role);
    assert.throws(()=>assertMessageSource({...message,source:message.role},persisted,message.role));
    assert.throws(()=>assertMessageSource(message,{...persisted,source:message.role},message.role));
  }
  evidence.message_sources='公开和PG的user_input/assistant_generation及created_at一致，role复制负哨兵被拒绝';
  evidence.stopped=await controller.stop();
  assert.equal(evidence.stopped.exit_code,0);
  assert.equal(evidence.stopped.running,false);
} finally {await controller.close();}
const names=execute('docker',['ps','-a','--filter',`name=^/${controller.resource.name}$`,'--format','{{.Names}}']);
assert.equal(names.code,0);assert.equal(names.stdout.trim(),'');
ctx.evidence('execution/controller-probe.json',{status:'passed',...evidence,closed:true});
console.log('控制器正负哨兵通过：错误身份拒绝清理、失败场景回收、无Worker清理、非法阶段、首片暂停、三片完成、main exit0、容器关闭');
