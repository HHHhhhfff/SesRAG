import {runCategory,assert,execute,repoRoot,smokeRoot} from '../lib/category-kit.mjs';
import path from 'node:path';
import {contractValidator} from '../lib/api-contracts.mjs';
import {categoryGate} from '../lib/quality-category-gate.mjs';
import {executionRows} from './execution-coverage.mjs';
import {documentRagRows} from './document-rag-coverage.mjs';
import {requiredBrowserCheckIds,requiredComponentCheckIds} from '../tooling/frontend-checks.mjs';
import {httpContractMatrix} from '../tooling/http-contract-matrix.mjs';
import {composeRagCheck} from '../tooling/compose-rag-check.mjs';
export const coveredCases=['QLT_001','QLT_002','QLT_003','QLT_004','QLT_005','QLT_006','QLT_007'];

await runCategory('qlt',async s=>{
 const c=s.ctx;
 await s.check('QLT_005','TP-QLT-005','compose-evidence-json','真实Context落盘含引号及跨平台traceback仍可解析且脱敏',()=>{
  const result=execute(process.execPath,['--test','tests/demo-smoke/tooling/compose-rag-check.test.mjs'],{timeoutMs:30000});
  c.evidence('qlt/compose-evidence-test.log',result.stdout+'\n'+result.stderr);assert.equal(result.code,0);return {exit_code:result.code};
 });
 await s.check('QLT_005','TP-QLT-005','root-compose-rag-consumption','根Compose四配置及API/Worker实际消费不可由Settings直接构造代替',()=>composeRagCheck(c));
 // QLT_001：预期表独立硬编码，不从受测私有转移表计算期待值；全边均执行真实函数。
 await s.check('QLT_001','TP-QLT-001','all-state-edges','全部合法边返回目标、所有其他边拒绝，含所有终态回退',()=>{
  const result=c.python(`import json\nfrom backend.domain.enums import RunState,TaskState\nfrom backend.domain.entities import transition_run,transition_task,InvalidTransitionError\nexpected_run={'queued':['running','cancelled','failed'],'running':['retry_waiting','succeeded','failed','cancelled'],'retry_waiting':['running','cancelled','failed'],'succeeded':[],'failed':[],'cancelled':[]}\nexpected_task={'queued':['leased','cancelled','failed'],'leased':['queued','running','retry_waiting','cancelled','failed'],'running':['queued','succeeded','retry_waiting','cancelled','failed'],'retry_waiting':['queued','cancelled','failed'],'succeeded':[],'failed':[],'cancelled':[]}\nrows=[]\nfor kind,enum,fn,allowed in [('run',RunState,transition_run,expected_run),('task',TaskState,transition_task,expected_task)]:\n for current in enum:\n  for target in enum:\n   should_allow=target.value in allowed[current.value];raised=False;value=None\n   try: value=fn(current,target)\n   except InvalidTransitionError: raised=True\n   passed=(not raised and value==target) if should_allow else raised\n   rows.append({'kind':kind,'from':current.value,'to':target.value,'expected_allowed':should_allow,'raised_invalid_transition':raised,'returned':None if value is None else value.value,'passed':passed})\nprint('SMOKE_JSON:'+json.dumps(rows))`);c.evidence('qlt/state-edge-matrix.json',result);assert.equal(result.length,85);assert.ok(result.every(x=>x.passed),'非法边必须实际抛InvalidTransitionError，不能静默返回current');return {edges:result.length,scope:'领域纯函数；不代表handler直接赋值或并发写回正确'};
 });
 // QLT002～005：实际执行既有门禁，完整专项缺口独立记录，不数文件宣称覆盖。
 const python=path.join(repoRoot,'.venv/Scripts/python.exe');
 const groups=[['QLT_002','TP-QLT-002',['tests/api/test_core_api.py'],'Journal与SSE'],['QLT_003','TP-QLT-003',['tests/integration/test_lease_recovery.py'],'既有SQLite租约（不替代PG）'],['QLT_004','TP-QLT-004',['tests/unit/test_task_policy.py'],'退避数值（不替代取消/回排）'],['QLT_005','TP-QLT-005',['tests/unit/test_parsers.py','tests/unit/test_chunker.py','tests/unit/test_vector_store.py','tests/integration/test_document_flow.py'],'既有解析向量主路径']];
 for(const [id,tp,files,title]of groups) {
  await s.check(id,tp,'existing-executable-gate',`真实执行${title}既有pytest门禁并保存退出/输出`,()=>{const r=execute(python,['-m','pytest','-q',...files],{timeoutMs:90000});c.evidence(`qlt/${id}-pytest.log`,r.stdout+'\n'+r.stderr);assert.equal(r.code,0,`${title}既有测试失败，见证据`);assert.match(r.stdout,/\d+ passed/);return {files,exit_code:r.code,summary:r.stdout.trim().split(/\r?\n/).at(-1)};});
  const categories={QLT_002:['evt','sse'],QLT_003:['wk'],QLT_004:['run','can'],QLT_005:['doc','par','chk','idx','rag']}[id];
  await s.check(id,tp,'complete-regression-gate','本run完整分类与所有新增必测ID、身份、Schema、证据逐项通过',async()=>{
   const results=[];for(const category of categories){
    const ids=[...executionRows,...documentRagRows].filter(row=>row[0].split('_')[0].toLowerCase()===category).map(row=>row.slice(0,3).join('__'));
    results.push(await categoryGate(c,category,ids));
   }return results;
  });
 }
 await s.check('QLT_006','TP-QLT-006','route-event-contract','全部公开路径/方法与接口基线一致，实际Event严格满足v1Schema',async()=>{
  const expected={'/api/v1/threads':['get','post'],'/api/v1/threads/{thread_id}':['get'],'/api/v1/threads/{thread_id}/archive':['post'],'/api/v1/threads/{thread_id}/messages':['post'],'/api/v1/runs/{run_id}':['get'],'/api/v1/runs/{run_id}/events':['get'],'/api/v1/runs/{run_id}/events/stream':['get'],'/api/v1/runs/{run_id}/cancel':['post'],'/api/v1/documents':['get','post'],'/api/v1/documents/{document_id}/index':['post'],'/health/live':['get'],'/health/ready':['get']};
  const schemaResponse=await c.request('/openapi.json');assert.equal(schemaResponse.status,200);const paths=Object.fromEntries(Object.entries(schemaResponse.body.paths).map(([p,item])=>[p,Object.keys(item).sort()]));assert.deepEqual(paths,expected);
  const ajv=contractValidator();const validate=ajv.getSchema('https://sesrag.local/contracts/run_event_v1.json');const t=await c.thread('QLT_006契约');const m=await c.submit(t.thread_id,'契约测试');await c.waitRun(m.run_id);const events=await c.events(m.run_id);for(const e of events)assert.ok(validate(e),JSON.stringify(validate.errors));
  c.evidence('qlt/openapi-event-contract.json',{paths,event_types:events.map(x=>x.type),schema_valid:true});return {paths: Object.keys(paths).length,events:events.length,run_id:m.run_id};
 });
 await s.check('QLT_006','TP-QLT-006','full-http-field-contract','全部正式HTTP成功/422/业务错误及Event联合契约和前端tmp生成diff',()=>httpContractMatrix(c));
 await s.check('QLT_006','TP-QLT-006','contract-negative-sentinels','错Event payload、类型漂移及安全未知type/loc都由真实门禁拒绝',()=>{
  const node=execute(process.execPath,['--test','tests/demo-smoke/tooling/contracts.test.mjs','tests/demo-smoke/lib/category-kit.test.mjs'],{timeoutMs:60000});
  const py=execute(python,['-m','pytest','-q','tests/demo-smoke/tooling/test_contract_fallback.py'],{timeoutMs:30000});
  c.evidence('qlt/contract-negative-sentinels.json',{node,py});assert.equal(node.code,0);assert.equal(py.code,0);return {node_exit:node.code,python_exit:py.code};
 });
 // QLT_007：每条质量命令独立检查，前一失败不阻断其余真实门禁。
 const backendCommands=[['pytest',['-m','pytest','-q','tests/unit','tests/api','tests/integration']],['ruff-check',['-m','ruff','check','backend','migrations','tests/unit','tests/api','tests/integration']],['ruff-format',['-m','ruff','format','--check','backend','migrations','tests/unit','tests/api','tests/integration']],['mypy',['-m','mypy','backend']]];
 for(const [name,args]of backendCommands)await s.check('QLT_007','TP-QLT-007',name,`${name}真实后端门禁执行并通过`,()=>{const r=execute(python,args,{timeoutMs:120000});c.evidence(`qlt/${name}.log`,r.stdout+'\n'+r.stderr);assert.equal(r.code,0,`${name}退出${r.code}，见原输出`);return {command:`python ${args.join(' ')}`,exit_code:r.code,summary:r.stdout.trim().split(/\r?\n/).at(-1)};});
 const frontendCommands=[['typecheck',['--prefix','frontend','run','typecheck']],['build',['--prefix','frontend','run','build']],['eslint',['--prefix','tests/demo-smoke','run','lint:frontend']],['vitest',['--prefix','tests/demo-smoke','run','unit:frontend','--','specific_test_script/fe-workspace.test.ts']]];
 const npmCli=path.join(path.dirname(process.execPath),'node_modules/npm/bin/npm-cli.js');
 for(const [name,args]of frontendCommands)await s.check('QLT_007','TP-QLT-008',name,`${name}是真实独立前端门禁，不能以vue-tsc冒充Lint或工具安装冒充测试`,()=>{const r=execute(process.execPath,[npmCli,'--cache',path.join(smokeRoot,'.cache/npm'),...args],{timeoutMs:120000});c.evidence(`qlt/frontend-${name}.log`,r.stdout+'\n'+r.stderr);assert.equal(r.code,0,`${name}退出${r.code}，见原输出；组件真实失败不能伪报门禁通过`);return {name,exit_code:r.code,summary:r.stdout.trim().split(/\r?\n/).at(-1)};});
 await s.check('QLT_007','TP-QLT-008','browser-category-gate','本run完整30浏览器和36组件必测集合通过；缺报告真实运行FE分类',()=>categoryGate(c,'fe',[...requiredBrowserCheckIds,...requiredComponentCheckIds]));
 // 正式all清理前采样：前述会停PG/Worker的检查均已finally恢复，不复用旧诊断依赖快照。
 await s.check('QLT_007','TP-QLT-007','actual-runtime-dependencies','本轮宿主/API/Worker实际版本分别记录且三端pip check真实exit0',()=>{
  const args=Object.entries(c.args).flatMap(([key,value])=>['-'+key,value]);
  const result=execute(process.execPath,[path.join(smokeRoot,'tooling/environment-evidence.mjs'),...args],{timeoutMs:120000});
  c.evidence('qlt/dependency-process.json',result);assert.equal(result.code,0,'本轮依赖采样或pip check失败，见原始证据');
  c.evidencePaths.push('evidence/qlt/dependency-versions.json');
  return {exit_code:result.code,versions_evidence:'evidence/qlt/dependency-versions.json',scope:'本轮运行中的host/API/Worker；不是旧诊断快照'};
 });
});
