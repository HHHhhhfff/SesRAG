import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { parseArgs, readCases, aggregateStatus, redact, safeChild, Suite, Context, smokeRoot, registerNestedRun } from './category-kit.mjs';
import * as categoryKit from './category-kit.mjs';
import {requireCategoryChecks} from './category-report-contract.mjs';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

// 报告工具自检：错误状态不能被通过项覆盖，路径/凭据不能进入证据。
test('分类状态保留失败和阻塞，空检查不得通过', () => {
  assert.equal(aggregateStatus([]), 'not_ready');
  assert.equal(aggregateStatus([{status:'passed'},{status:'failed'}]), 'failed');
  assert.equal(aggregateStatus([{status:'passed'},{status:'blocked'}]), 'blocked');
  assert.equal(aggregateStatus([{status:'passed'}]), 'passed');
});
test('Suite真实失败/阻塞不中断后项，附加证据可追溯且身份检查拒绝',async()=>{
 const cache=path.join(smokeRoot,'.cache');fs.mkdirSync(cache,{recursive:true});const directory=fs.mkdtempSync(path.join(cache,'category-self-'));
 try {
  const ctx=Object.assign(Object.create(Context.prototype),{args:{ArtifactDir:directory,RunId:'self-check'},secrets:[],evidencePaths:[]});
  const s=new Suite('self-test',ctx);s.note=()=>{};
  await s.check('DEP_001','TP-DEP-001','failure','预期真实拒绝',()=>{ctx.evidence('self-extra.json',{test:'附加中文证据'});assert.equal('错误实际值','正确预期值');});
  await s.check('DEP_001','TP-DEP-002','success','失败之后仍执行',()=>({中文:'已执行'}));
  s.block('DEP_003','TP-DEP-004','blocked','完整故障场景','缺少故障驱动');
  await assert.rejects(s.check('DEP_001','TP-DEP-002','success','重复',()=>true),/重复/);
  await assert.rejects(s.check('DEP_001','TP-HLT-001','wrong-point','错关联',()=>true),/未知/);
  const report=s.finish();assert.equal(report.status,'failed');assert.deepEqual(report.checks.map(x=>x.status),['failed','passed','blocked']);
  assert.ok(report.checks[0].evidence.includes('evidence/self-extra.json'));assert.equal(report.run_id,'self-check');
  const ajv=new Ajv2020();addFormats(ajv);const validate=ajv.compile(JSON.parse(fs.readFileSync(path.join(smokeRoot,'specific_test_script/category-result.schema.json'),'utf8')));assert.ok(validate(report),JSON.stringify(validate.errors));
  assert.equal(JSON.parse(fs.readFileSync(path.join(directory,'categories/self-test.json'),'utf8')).checks.length,3);
 } finally {assert.equal(path.dirname(directory),cache);fs.rmSync(directory,{recursive:true});}
});
test('六参数缺失拒绝且可完整读取', () => {
  assert.throws(() => parseArgs([]), /缺少/);
  const values = ['BaseUrl','FrontendUrl','RunId','ArtifactDir','RuntimeDir','FixtureDir'];
  const args = parseArgs(values.flatMap(x=>['-'+x,'x']));
  assert.equal(args.RunId, 'x');
});
test('嵌套登记保持父身份、去重，拒绝主环境目标与错误标记',()=>{
 const root=path.join(smokeRoot,'.cache');fs.mkdirSync(root,{recursive:true});const dir=fs.mkdtempSync(path.join(root,'nested-register-'));
 try {
  const ctx={args:{RunId:'parent-run',RuntimeDir:dir},context:{compose_project:'sesrag-demo-smoke-parent'}};
  const state={marker:'sesrag-demo-smoke-v1',run_id:'child-run',compose_project:'sesrag-demo-smoke-child'};
  registerNestedRun(ctx,state);registerNestedRun(ctx,state);
  const record=JSON.parse(fs.readFileSync(path.join(dir,'nested-runs.json'),'utf8'));assert.equal(record.parent_run_id,'parent-run');assert.equal(record.nested.length,1);assert.equal(record.nested[0].compose_project,state.compose_project);
  assert.throws(()=>registerNestedRun(ctx,{...state,run_id:'parent-run'}));
  assert.throws(()=>registerNestedRun(ctx,{...state,marker:'wrong'}));
  assert.throws(()=>registerNestedRun(ctx,{...state,compose_project:'sesrag-demo-smoke-parent'}));
 } finally {assert.equal(path.dirname(dir),root);fs.rmSync(dir,{recursive:true});}
});
test('用例解析完整，联合目标不丢失', () => {
  const cases = readCases();
  assert.equal(cases.size,149);
  assert.deepEqual(cases.get('DEP_001').points,['TP-DEP-001','TP-DEP-002']);
  assert.equal(cases.get('LIFE_009').state,'可验证·本机动态');
});
test('嵌套登记I/O失败不崩出stdout回调，保留精确身份供finally恢复',()=>{
 assert.equal(typeof categoryKit.createNestedRunObserver,'function','需要有界捕获stdout观察错误的真实适配器');
 const {createNestedRunObserver}=categoryKit;
 const root=path.join(smokeRoot,'.cache');fs.mkdirSync(root,{recursive:true});const dir=fs.mkdtempSync(path.join(root,'nested-observer-'));
 try {
  const parent=path.join(dir,'parent');const child=path.join(dir,'child-run');fs.mkdirSync(parent);fs.mkdirSync(child);
  fs.writeFileSync(path.join(child,'context.json'),JSON.stringify({marker:'sesrag-demo-smoke-v1',run_id:'child-run',compose_project:'sesrag-demo-smoke-child'}));
  fs.writeFileSync(path.join(parent,'nested-runs.json'),'invalid-json');
  const ctx={args:{RunId:'parent-run',RuntimeDir:parent},context:{compose_project:'sesrag-demo-smoke-parent'}};
  const observer=createNestedRunObserver(ctx,dir);
  assert.doesNotThrow(()=>observer.observe('Run: child-run；project: sesrag-demo-smoke-child\n'));
  assert.equal(observer.runId,'child-run');assert.equal(observer.project,'sesrag-demo-smoke-child');assert.ok(observer.error instanceof Error);
  // 主身份或坏标记不能获得可销毁权限；保留错误，不吞成成功。
  fs.writeFileSync(path.join(parent,'nested-runs.json'),JSON.stringify({schema_version:1,parent_run_id:'parent-run',nested:[]}));
  const valid=createNestedRunObserver(ctx,dir);valid.observe('Run: child-run；project: sesrag-demo-smoke-child\n');assert.equal(valid.error,undefined);
  assert.equal(JSON.parse(fs.readFileSync(path.join(parent,'nested-runs.json'))).nested[0].run_id,'child-run');
  const main=createNestedRunObserver(ctx,dir);assert.doesNotThrow(()=>main.observe('Run: parent-run；project: sesrag-demo-smoke-parent\n'));assert.ok(main.error);
  const split=createNestedRunObserver(ctx,dir);split.observe('Run: child-run；project: sesrag-demo-smoke-ch');assert.equal(split.runId,undefined);split.observe('ild\n');assert.equal(split.project,'sesrag-demo-smoke-child');assert.equal(split.error,undefined);
 }finally {assert.equal(path.dirname(dir),root);fs.rmSync(dir,{recursive:true});}
});
test('分类辅助进程超时终止整棵自有树并保留中文输出/真实退出',async()=>{
 assert.equal(typeof categoryKit.executeTree,'function','辅助FE必须使用进程树有界适配器');
 const source="const {spawn}=require('node:child_process'); const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{windowsHide:true}); console.log('CHILD_PID:'+child.pid); console.log('中文树探针'); setInterval(()=>{},1000);";
 const observed=await categoryKit.executeTree(process.execPath,['-e',source],{timeoutMs:1000});
 assert.equal(observed.code,124);assert.equal(observed.timed_out,true);assert.match(observed.stdout,/中文树探针/);
 const pid=Number(observed.stdout.match(/CHILD_PID:(\d+)/)?.[1]);assert.ok(pid>0);
 assert.throws(()=>process.kill(pid,0),error=>error.code==='ESRCH','子进程树不可残留');
 const failed=await categoryKit.executeTree(process.execPath,['-e','process.exit(7)'],{timeoutMs:1000});assert.equal(failed.code,7);assert.equal(failed.timed_out,false);
});
test('浏览器门禁拒绝部分报告、错误身份和非法Schema，不混完整场景blocked',()=>{
 const id='FE_001__TP-FE-001__browser-main';
 const report={schema_version:1,run_id:'report-run',category:'fe',status:'blocked',started_at:'2026-10-07T00:00:00Z',finished_at:'2026-10-07T00:00:01Z',checks:[{id,test_point_id:'TP-FE-001',status:'passed',expected:'实际浏览器检查',actual:'通过',evidence:[]},{id:'FE_009__TP-FE-010__full-scenario',test_point_id:'TP-FE-010',status:'blocked',expected:'完整条件',actual:'缺少条件',evidence:[]}],evidence:[]};
 assert.equal(requireCategoryChecks(report,'report-run','fe',[id]).length,1);
 assert.throws(()=>requireCategoryChecks({...report,checks:[]},'report-run','fe',[id]),/集合不完整/);
 assert.throws(()=>requireCategoryChecks({...report,category:'wrong'},'report-run','fe',[id]));
 assert.throws(()=>requireCategoryChecks({...report,checks:[{...report.checks[0],actual:42}]},'report-run','fe',[id]),/Schema/);
 assert.throws(()=>requireCategoryChecks({...report,checks:[report.checks[0],report.checks[0]]},'report-run','fe',[id]),/重复/);
});
test('精确子目录限制与凭据脱敏', () => {
  assert.throws(()=>safeChild('D:/tmp/test','../escape'),/越界/);
  assert.throws(()=>safeChild('D:/tmp/test','D:/escape'),/越界/);
  assert.ok(!redact('postgresql://user:abc123@host/db Bearer ABC_TOKEN').includes('abc123'));
  assert.ok(!redact('Bearer ABC_TOKEN').includes('ABC_TOKEN'));
  assert.ok(!redact('{"model_api_key":"JSON_SENTINEL"}').includes('JSON_SENTINEL'));
  assert.ok(!redact('{"password":"JSON_PASSWORD"}').includes('JSON_PASSWORD'));
  assert.ok(redact('Expected to be equal:\n+ actual').includes('equal'));
  assert.ok(redact({actual:'Expected to be equal:\n+ actual'}).includes('equal'));
});
test('真实HTTP socket异常保留传输错误码，不自动重试或冒充HTTP响应',async()=>{
 let requests=0;const sockets=new Set();const server=http.createServer(request=>{requests++;request.socket.destroy();});server.on('connection',socket=>{sockets.add(socket);socket.on('close',()=>sockets.delete(socket));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try {
  const ctx=Object.assign(Object.create(Context.prototype),{args:{BaseUrl:`http://127.0.0.1:${server.address().port}`},secrets:[]});
  await assert.rejects(ctx.request('/network-probe',{method:'POST',body:{safe:true}}),error=>/HTTP传输未完成/.test(error.message)&&/UND_ERR_SOCKET|ECONNRESET/.test(error.message));assert.equal(requests,1);
 }finally{for(const socket of sockets)socket.destroy();await new Promise(resolve=>server.close(resolve));}
});
