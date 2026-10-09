import {runCategory,assert,execute,executeTree,repoRoot,smokeRoot} from '../lib/category-kit.mjs';
import path from 'node:path';
import fs from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {requireCategoryChecks} from '../lib/category-report-contract.mjs';
export const coveredCases=['QLT_001','QLT_002','QLT_003','QLT_004','QLT_005','QLT_006','QLT_007'];

await runCategory('qlt',async s=>{
 const c=s.ctx;
 // QLT_001：预期表独立硬编码，不从受测私有转移表计算期待值；全边均执行真实函数。
 await s.check('QLT_001','TP-QLT-001','all-state-edges','全部合法边返回目标、所有其他边拒绝，含所有终态回退',()=>{
  const result=c.python(`import json\nfrom backend.domain.enums import RunState,TaskState\nfrom backend.domain.entities import transition_run,transition_task,InvalidTransitionError\nexpected_run={'queued':['running','cancelled'],'running':['retry_waiting','succeeded','failed','cancelled'],'retry_waiting':['running','cancelled','failed'],'succeeded':[],'failed':[],'cancelled':[]}\nexpected_task={'queued':['leased','cancelled'],'leased':['running','retry_waiting','cancelled','failed'],'running':['succeeded','retry_waiting','cancelled','failed'],'retry_waiting':['queued','cancelled','failed'],'succeeded':[],'failed':[],'cancelled':[]}\nrows=[]\nfor kind,enum,fn,allowed in [('run',RunState,transition_run,expected_run),('task',TaskState,transition_task,expected_task)]:\n for current in enum:\n  for target in enum:\n   should_allow=target.value in allowed[current.value];raised=False;value=None\n   try: value=fn(current,target)\n   except InvalidTransitionError: raised=True\n   passed=(not raised and value==target) if should_allow else raised\n   rows.append({'kind':kind,'from':current.value,'to':target.value,'expected_allowed':should_allow,'raised_invalid_transition':raised,'returned':None if value is None else value.value,'passed':passed})\nprint('SMOKE_JSON:'+json.dumps(rows))`);c.evidence('qlt/state-edge-matrix.json',result);assert.equal(result.length,85);assert.ok(result.every(x=>x.passed),'非法边必须实际抛InvalidTransitionError，不能静默返回current');return {edges:result.length,scope:'领域纯函数；不代表handler直接赋值或并发写回正确'};
 });
 // QLT002～005：实际执行既有门禁，完整专项缺口独立记录，不数文件宣称覆盖。
 const python=path.join(repoRoot,'.venv/Scripts/python.exe');
 const groups=[['QLT_002','TP-QLT-002',['tests/api/test_core_api.py'],'Journal与SSE'],['QLT_003','TP-QLT-003',['tests/integration/test_lease_recovery.py'],'既有SQLite租约（不替代PG）'],['QLT_004','TP-QLT-004',['tests/unit/test_task_policy.py'],'退避数值（不替代取消/回排）'],['QLT_005','TP-QLT-005',['tests/unit/test_parsers.py','tests/unit/test_chunker.py','tests/unit/test_vector_store.py','tests/integration/test_document_flow.py'],'既有解析向量主路径']];
 for(const [id,tp,files,title]of groups) {
  await s.check(id,tp,'existing-executable-gate',`真实执行${title}既有pytest门禁并保存退出/输出`,()=>{const r=execute(python,['-m','pytest','-q',...files],{timeoutMs:90000});c.evidence(`qlt/${id}-pytest.log`,r.stdout+'\n'+r.stderr);assert.equal(r.code,0,`${title}既有测试失败，见证据`);assert.match(r.stdout,/\d+ passed/);return {files,exit_code:r.code,summary:r.stdout.trim().split(/\r?\n/).at(-1)};});
  const limitation={QLT_002:'本轮EVT/SSE常规检查已接，但并发seq和事务回滚屏障完整门禁未备。',QLT_003:'现有pytest是SQLite，WK真实PG正常领取已补，但多Worker/过期回收/旧写回完整PG门禁未备。',QLT_004:'本轮queued取消与退避已补，retry_waiting回排/耗尽及running取消竞态尚未完整落地。',QLT_005:'本轮三格式/切分/召回引用已补，candidate构建/事务发布屏障及真实Provider故障完整门禁未备。'}[id];
  s.block(id,tp,'complete-regression-gate',s.cases.get(id).expected,limitation);
 }
 await s.check('QLT_006','TP-QLT-006','route-event-contract','全部公开路径/方法与接口基线一致，实际Event严格满足v1Schema',async()=>{
  const expected={'/api/v1/threads':['get','post'],'/api/v1/threads/{thread_id}':['get'],'/api/v1/threads/{thread_id}/archive':['post'],'/api/v1/threads/{thread_id}/messages':['post'],'/api/v1/runs/{run_id}':['get'],'/api/v1/runs/{run_id}/events':['get'],'/api/v1/runs/{run_id}/events/stream':['get'],'/api/v1/runs/{run_id}/cancel':['post'],'/api/v1/documents':['get','post'],'/api/v1/documents/{document_id}/index':['post'],'/health/live':['get'],'/health/ready':['get']};
  const schemaResponse=await c.request('/openapi.json');assert.equal(schemaResponse.status,200);const paths=Object.fromEntries(Object.entries(schemaResponse.body.paths).map(([p,item])=>[p,Object.keys(item).sort()]));assert.deepEqual(paths,expected);
  const ajv=new Ajv2020({allErrors:true});addFormats(ajv);const validate=ajv.compile(JSON.parse(fs.readFileSync(path.join(repoRoot,'contracts/run_event_v1.json'),'utf8')));const t=await c.thread('QLT_006契约');const m=await c.submit(t.thread_id,'契约测试');await c.waitRun(m.run_id);const events=await c.events(m.run_id);for(const e of events)assert.ok(validate(e),JSON.stringify(validate.errors));
  c.evidence('qlt/openapi-event-contract.json',{paths,event_types:events.map(x=>x.type),schema_valid:true});return {paths: Object.keys(paths).length,events:events.length,run_id:m.run_id};
 });
 s.block('QLT_006','TP-QLT-006','full-http-field-contract','所有HTTP成功/异常响应及前端类型逐字段全契约门禁','本轮路径方法/Event动态Schema已测；完整HTTP响应JSON Schema与自动前端类型生成仍未实施，不能用OpenAPI存在替代全部响应检查。');
 // QLT_007：每条质量命令独立检查，前一失败不阻断其余真实门禁。
 const backendCommands=[['pytest',['-m','pytest','-q','tests/unit','tests/api','tests/integration']],['ruff-check',['-m','ruff','check','backend','migrations','tests/unit','tests/api','tests/integration']],['ruff-format',['-m','ruff','format','--check','backend','migrations','tests/unit','tests/api','tests/integration']],['mypy',['-m','mypy','backend']]];
 for(const [name,args]of backendCommands)await s.check('QLT_007','TP-QLT-007',name,`${name}真实后端门禁执行并通过`,()=>{const r=execute(python,args,{timeoutMs:120000});c.evidence(`qlt/${name}.log`,r.stdout+'\n'+r.stderr);assert.equal(r.code,0,`${name}退出${r.code}，见原输出`);return {command:`python ${args.join(' ')}`,exit_code:r.code,summary:r.stdout.trim().split(/\r?\n/).at(-1)};});
 const frontendCommands=[['typecheck',['--prefix','frontend','run','typecheck']],['build',['--prefix','frontend','run','build']],['eslint',['--prefix','tests/demo-smoke','run','lint:frontend']],['vitest',['--prefix','tests/demo-smoke','run','unit:frontend','--','specific_test_script/fe-workspace.test.ts']]];
 const npmCli=path.join(path.dirname(process.execPath),'node_modules/npm/bin/npm-cli.js');
 for(const [name,args]of frontendCommands)await s.check('QLT_007','TP-QLT-008',name,`${name}是真实独立前端门禁，不能以vue-tsc冒充Lint或工具安装冒充测试`,()=>{const r=execute(process.execPath,[npmCli,'--cache',path.join(smokeRoot,'.cache/npm'),...args],{timeoutMs:120000});c.evidence(`qlt/frontend-${name}.log`,r.stdout+'\n'+r.stderr);assert.equal(r.code,0,`${name}退出${r.code}，见原输出；组件真实失败不能伪报门禁通过`);return {name,exit_code:r.code,summary:r.stdout.trim().split(/\r?\n/).at(-1)};});
 await s.check('QLT_007','TP-QLT-008','browser-category-gate','Playwright产品断言真实接入并有逐项报告，非浏览器工具探针',async()=>{
  const reportPath=path.join(c.args.ArtifactDir,'categories/fe.json');
  // QLT_007独立运行不依赖另一用例成功；未有本run FE报告则调用同一真实分类并保存退出/证据。
  if(!fs.existsSync(reportPath)){
   const args=Object.entries(c.args).flatMap(([key,value])=>['-'+key,value]);
   const result=await executeTree(process.execPath,[path.join(smokeRoot,'specific_test_script/fe-tests.mjs'),...args],{timeoutMs:420000,env:{PLAYWRIGHT_BROWSERS_PATH:path.join(smokeRoot,'.cache/ms-playwright')}});
   c.evidence('qlt/standalone-fe.log',result.stdout+'\n'+result.stderr);
   c.evidence('qlt/standalone-fe-process.json',{exit_code:result.code,timed_out:result.timed_out,launch_error:result.error??null});
   s.note(`QLT_007独立浏览器分类结束：真实退出${result.code}，产品失败保留逐项报告`);
   assert.ok(!result.error&&!result.timed_out&&[0,1,2].includes(result.code),'独立FE启动/超时异常，不允许用已有部分报告当门禁通过');
   assert.ok(fs.existsSync(reportPath),'独立FE未产生报告，不能算产品通过');
  }
  const expectedBrowserIds=['FE_001__TP-FE-001__browser-http-upload-sse','FE_001__TP-FE-002__browser-create-select','FE_002__TP-FE-003__browser-no-thread','FE_002__TP-FE-003__browser-empty-input','FE_002__TP-FE-003__browser-button','FE_002__TP-FE-003__browser-ctrl-enter','FE_004__TP-FE-005__browser-no-refresh','FE_006__TP-FE-007__browser-request-failure','FE_007__TP-FE-008__browser-normal-timeline','FE_009__TP-FE-010__browser-disconnect-no-cancel','FE_009__TP-FE-010__browser-reconnect-entry','FE_011__TP-FE-012__browser-terminal-restore','FE_012__TP-FE-013__browser-indexed-initial','FE_012__TP-FE-013__browser-indexed-automatic-terminal','FE_012__TP-FE-013__browser-failed-initial','FE_012__TP-FE-013__browser-failed-automatic-terminal','FE_013__TP-FE-014__browser-citation-label','FE_013__TP-FE-014__browser-citation-expand','FE_014__TP-FE-016__browser-health-panels'];
  const report=JSON.parse(fs.readFileSync(reportPath,'utf8'));const browser=requireCategoryChecks(report,c.args.RunId,'fe',expectedBrowserIds);assert.ok(browser.every(x=>x.status==='passed'),`Playwright ${browser.filter(x=>x.status==='failed').length}真实失败、${browser.filter(x=>x.status==='blocked').length}受阻，不能宣称门禁全通过`);return {browser_checks:browser.length,status:report.status};
 });
});
