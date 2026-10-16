import { assert } from '../lib/category-kit.mjs';
import { pgScenario } from '../tooling/pg-execution.mjs';
import fs from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';

const validateEvidence=new Ajv2020({strict:true}).compile(JSON.parse(fs.readFileSync(new URL('../../../contracts/evidence_v1.json',import.meta.url),'utf8')));

// 同case可复用同场景证据；不同case始终重新建独立数据库和业务身份。
export const documentRagRows = [
 ['DOC_006','TP-DOC-007','full-scenario','document-commit-failure','保存后登记commit失败：HTTP503、事实回滚、source/tmp清理'],
 ['DOC_007','TP-DOC-008','full-scenario','document-write-failure','本例tmp部分写失败：HTTP503、无事实/残留，恢复正常上传'],
 ...['leased','running','retry_waiting'].map(s=>['DOC_008','TP-DOC-010',s,'document-reuse-'+s.replaceAll('_','-'),`${s}真实阶段重复索引复用同Task/batch`]),
 ['DOC_009','TP-DOC-011','deterministic-query-barrier','document-lock','两个真实连接同时等待Document锁，锁后复查唯一活动Task'],
 ['CHK_002','TP-CHK-003','worker-config-settlement','chunk-invalid-config','正式Settings启动边界和chunker均拒绝非法配置，禁止绕过校验塞入Worker'],
 ['PAR_003','TP-IDX-008','ordinary-error-exhaustion','parser-ordinary-exhaustion','普通Parser异常真实重试至上限，Task/Document一致failed'],
 ['IDX_002','TP-IDX-003','indexing-phase','index-candidate-first','真实第二块Embedding暂停时Document indexing且Task running'],
 ...['383','385'].map(d=>['IDX_003','TP-IDX-002','dimension-'+d,'provider-index-'+d,`HTTP ${d}维进入正式index Runtime并安全拒绝发布`]),
 ['IDX_003','TP-IDX-002','dimension-384-control','provider-index-valid','真实HTTP384维对照成功，真实候选正常发布'],
 ...['first','rebuild'].map(m=>['IDX_004','TP-IDX-004','candidate-inflight-'+m,'index-candidate-'+m,'构建期间真实search只能读旧active，首次候选不可见；成功才切换']),
 ['IDX_004','TP-IDX-006','failed-rebuild-old-active','index-candidate-failed','第N块失败保留旧active/Chunk身份与检索证据'],
 ['IDX_005','TP-IDX-005','commit-window','index-publication-commit','最终flush后commit故障整组回滚，无Task/Document半发布'],
 ['IDX_005','TP-IDX-008','ordinary-exhaustion','index-ordinary-exhaustion','普通Embedding异常真实耗尽且Task/Document一致failed'],
 ['IDX_007','TP-IDX-010','full-scenario','index-candidate-rebuild','慢Embedding期间独立engine多次pg_stat_activity无贯穿事务'],
 ...['one','over-n','zero','negative'].map(k=>['RAG_001','TP-RAG-014','runtime-top-k-config-'+k,'rag-top-k-'+k,'正式配置K=1/N+2正确消费，0/-1启动拒绝']),
 ...['permanent','transient'].map(m=>['RAG_002','TP-RAG-003','task-run-settlement-'+m,'rag-search-'+m,'真实search后异常经Runtime有界结算，不伪装无知识成功']),
 ['RAG_002','TP-RAG-003','query-wrong-dimension-settlement','provider-embed-383','真实HTTP错维查询安全失败，Run/Task/Event/Message一致'],
 ...['base','key','model','embedding','all','mock'].map(k=>['RAG_005','TP-RAG-009','container-startup-config-'+k,'rag-config-'+k,'当前源码容器独立解释器加载生产Worker入口，缺配置安全拒绝/Mock对照']),
 ['RAG_008','TP-RAG-013','full-scenario','provider-three-fragments','真实stream=true三片分别在HTTP未结束前持久Journal，DONE后准确最终正文'],
 ['SEC_004','TP-SEC-004','exception-sentinel-storage','document-write-failure','存储异常原始HTTP输出在Context脱敏前无合成敏感哨兵'],
 ['SEC_004','TP-SEC-005','exception-sentinel-provider','provider-chat-status-401','Provider原始HTTP/PG/Message/Event/Task/snapshot/默认日志在脱敏前无哨兵'],
 ['ARC_002','TP-ARC-002','replacement-provider-integration','rag-ports','替换Embedding/Model包装adapter后真实索引/Run消费正式证据'],
 ['ARC_002','TP-ARC-003','replacement-integration','rag-ports','替换Parser/Queue/Vector包装adapter后PG身份/来源/引用一致'],
];
for(const endpoint of ['embed','chat']) {
 for(const mode of ['status-400','status-401','status-403','status-404','status-408','status-429','status-500','status-503','timeout','socket','refused']) {
  const temporary=['status-408','status-429','status-500','status-503','timeout','socket','refused'].includes(mode);
  documentRagRows.push(['RAG_006',temporary?'TP-RAG-010':'TP-RAG-011',`${endpoint}-${mode}`,`provider-${endpoint}-${mode}`,`${endpoint}真实HTTP ${mode}：${temporary?'三次持久退避耗尽':'一次永久失败'}，稳定错误且无assistant`]);
 }
}
for(const [endpoint,modes] of [['embed',['non-json','missing','empty','wrong-data','missing-embedding','wrong-vector','383','385','non-numeric','non-finite','boolean','huge']],['chat',['non-json','missing','empty','wrong-choices','wrong-delta','wrong-content','missing-content','empty-content','missing-done']]])
 for(const mode of modes) documentRagRows.push(['RAG_007','TP-RAG-012',`${endpoint}-${mode}`,`provider-${endpoint}-${mode}`,`${endpoint}协议fixture ${mode}经过生产httpx/Runtime安全失败，无原文泄露或无意义成功`]);
for(const mode of ['status-400','status-500']) documentRagRows.push(['RAG_006',mode==='status-400'?'TP-RAG-011':'TP-RAG-010',`index-${mode}`,`provider-index-${mode}`,'真实HTTP索引错误Task/Document按永久/临时分类一致结算']);

export async function documentRagCoverage(suite, onlySub) {
 const selected=documentRagRows.filter(row=>row[0].split('_')[0].toLowerCase()===suite.name&&(!onlySub||onlySub.split(',').includes(row[2])));
 assert.ok(selected.length,'专项筛选必须命中实际检查');
 const cache=new Map();
 for(const [id,tp,sub,scenario,expected] of selected) await suite.check(id,tp,sub,expected,async()=>{
  const key=`${id}:${scenario}`;
  if(!cache.has(key)) cache.set(key,pgScenario(suite.ctx,scenario));
  const report=await cache.get(key);
  suite.ctx.evidencePaths.push(...report.evidence);
  assert.equal(report.scenario,scenario); assert.ok(report.assertions.length);
  if(report.trace.citations) for(const citation of report.trace.citations) assert.ok(validateEvidence(citation),JSON.stringify(validateEvidence.errors));
  const selectors={'IDX_002':'第二块','IDX_007':'pg_stat_activity','SEC_004':'原始','ARC_002':tp==='TP-ARC-002'?'真实索引与Run全部成功':'身份|来源|引用'};
  const assertions=selectors[id]?report.assertions.filter(a=>new RegExp(selectors[id]).test(a)):report.assertions;
  assert.ok(assertions.length,'该TP的独立实际断言未执行');
  if(id==='ARC_002') for(const key of tp==='TP-ARC-002'?['embed','model']:['parse','replace','search','claim']) assert.ok(report.trace.port_calls[key]>0,`替换${key}未实际消费`);
  return {scenario,database:report.database,assertions,protocol:report.trace.fixture??null};
 });
}
