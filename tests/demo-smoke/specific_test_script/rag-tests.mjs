import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {runCategory,assert,executeNestedScenario} from '../lib/category-kit.mjs';

export const coveredCases=['RAG_001','RAG_002','RAG_003','RAG_004','RAG_005','RAG_006','RAG_007','RAG_008'];
const driver=fs.readFileSync(new URL('./rag-driver.py',import.meta.url),'utf8');
const python=(ctx,params)=>ctx.python(`SMOKE_INPUT=__import__('json').loads(${JSON.stringify(JSON.stringify(params))})\n${driver}`);

await runCategory('rag',async s=>{
  const c=s.ctx;let search;
  // RAG_001：本例自建多块资料，Top-K按真实PG当前owner全部active集合计算。
  await s.check('RAG_001','TP-RAG-001','top-k-sort','真实search有效K返回min(K,N)，独立余弦得分降序',async()=>{
    const question='RAG_001安全多块查询资料';const r=await c.upload(`RAG_001-${randomUUID()}.txt`,Buffer.from((question+' 中英🙂\n').repeat(150)));assert.equal(r.status,201);assert.equal((await c.waitDoc(r.body.document_id,30000)).status,'indexed');
    search=python(c,{mode:'search',question});assert.ok(search.n>=3);for(const group of search.groups.filter(x=>x.k>0)){assert.equal(group.error,null);assert.equal(group.items.length,Math.min(group.k,search.n));const scores=group.items.map(x=>x.score);assert.deepEqual(scores,[...scores].sort((a,b)=>b-a));assert.ok(group.items.every(x=>x.score_matches));}return {document_id:r.body.document_id,n:search.n,groups:search.groups.filter(x=>x.k>0).map(x=>({k:x.k,count:x.items.length}))};
  });
  await s.check('RAG_001','TP-RAG-001','evidence-fields','Evidence文档/chunk/text/filename/offset/score匹配真实active Chunk',async()=>{
    assert.ok(search);const group=search.groups.find(x=>x.k===search.default_k);assert.ok(group.items.length);for(const item of group.items){assert.ok(item.identity_matches&&item.active_matches&&item.score_matches);assert.ok(item.document_id&&item.chunk_id&&item.filename);assert.ok(Number.isFinite(item.score));assert.ok(item.start_offset>=0&&item.end_offset>item.start_offset);}return {count:group.items.length,evidence:group.items.map(x=>({document_id:x.document_id,chunk_id:x.chunk_id,score:x.score}))};
  });
  await s.check('RAG_001','TP-RAG-008','cosine-and-no-threshold','余弦同向1/正交0/反向-1/零向量0，有库无关问题按现有无阈值Top-K返回',async()=>{
    const cosine=python(c,{mode:'cosine'});assert.deepEqual(cosine.checks.map(x=>x.score),[1,0,-1,0]);assert.equal(cosine.dimension_error,'ValueError');const unrelated=python(c,{mode:'search',question:'完全无关的RAG_001安全问题'}),items=unrelated.groups.find(x=>x.k===unrelated.default_k).items;assert.equal(items.length,Math.min(unrelated.default_k,unrelated.n));return {cosine_scores:cosine.checks.map(x=>x.score),unrelated_count:items.length,semantic_limit:'Mock无相关性阈值，不证明语义拒答'};
  });
  for(const k of [1,'over-n',0,-1])await s.check('RAG_001','TP-RAG-014',`k-${k}`,'有效K有界返回；K<=0必须明确拒绝且不采用负切片',async()=>{
    assert.ok(search);const group=k==='over-n'?search.groups.find(x=>x.k===search.n+2):search.groups.find(x=>x.k===k);assert.ok(group);if(typeof k==='number'&&k<=0)assert.ok(group.error,'当前search_chunks未拒绝K<=0，使用Python切片产生未约定行为');else{assert.equal(group.error,null);assert.equal(group.items.length,Math.min(group.k,search.n));}return {k:group.k,count:group.items.length,error:group.error};
  });
  s.block('RAG_001','TP-RAG-014','runtime-top-k-config','正式Worker配置K=1/N+2/0/-1正确验收','真实search函数边界已动态断言；缺少独立Worker配置驱动，不把函数调用等同正式Run配置验收。');
  // RAG_002：真实错维查询函数不得吞错；完整Task/Run重试结算仍需E2驱动。
  await s.check('RAG_002','TP-RAG-003','real-search-wrong-dimension','真实active集合错query维度抛明确错误而非返回空证据',async()=>{
    const r=await c.upload(`RAG_002-${randomUUID()}.txt`,Buffer.from('RAG_002错维查询对照'));assert.equal(r.status,201);assert.equal((await c.waitDoc(r.body.document_id,30000)).status,'indexed');const result=python(c,{mode:'dimension-error'});assert.equal(result.query_dimensions,383);assert.equal(result.error,'ValueError');return {document_id:r.body.document_id,...result};
  });
  s.block('RAG_002','TP-RAG-003','task-run-settlement','向量/查询故障Run/Task/Event/Message有限重试并失败，不伪无证据','真实search错维拒绝已验证；缺少E2错误Provider/真实search异常的正式Run驱动，且回排闭环缺口待验证。');
  await s.check('RAG_003','TP-RAG-004','isolated-empty-owner','真实PG空owner召回count0/items空，生产Mock明确无足够证据',async()=>{
    const result=python(c,{mode:'empty'});assert.equal(result.count,0);assert.deepEqual(result.items,[]);assert.ok(result.answer.includes('没有足够证据'));assert.equal(result.deltas.join('').trim(),result.answer);return {count:0,items:[],answer:result.answer,scope:'真实search+生产Mock空证据分支，随机独立空owner'};
  });
  await s.check('RAG_003','TP-RAG-004','formal-run-empty-range','独立全新库正式Run/Task succeeded，Journal空召回、最终Message明确无证据且引用空',async()=>{
    const nested=await executeNestedScenario(c,'rag-empty');assert.equal(nested.summary.status,'passed');assert.equal(nested.cleanup.status,'passed');assert.ok(nested.report);assert.equal(nested.report.category,'rag-empty');assert.equal(nested.report.status,'passed');const target=nested.report.checks.find(x=>x.id==='RAG_003__TP-RAG-004__formal-empty-run');assert.ok(target);assert.equal(target.status,'passed');const actual=typeof target.actual==='string'?JSON.parse(target.actual):target.actual;assert.equal(actual.retrieval_count,0);assert.deepEqual(actual.citations,[]);assert.equal(actual.run_status,'succeeded');assert.equal(actual.task_state,'succeeded');assert.ok(actual.deltas>0&&actual.run_id&&actual.task_id&&actual.message_id);assert.deepEqual(actual.initial_empty,{documents:0,chunks:0,threads:0,runs:0});assert.ok(nested.report.checks.length&&nested.report.checks.every(x=>x.status==='passed'));return {scenario:'rag-empty',nested_run_id:nested.report.run_id,checks:nested.report.checks.map(x=>({id:x.id,status:x.status})),run_status:actual.run_status,task_state:actual.task_state,retrieval_count:actual.retrieval_count,citations:actual.citations,cleanup:nested.cleanup.status,evidence:'evidence/nested/rag-empty-summary.json'};
  });
  const answer={};
  // RAG_004：此例独立三格式；问题等于本例txt内容，确保至少一个自建chunk进入召回。
  await s.check('RAG_004','TP-RAG-005','nonempty-evidence-answer','自建三格式真实索引，正式Run检索非空并基于本次召回证据回答',async()=>{
    const f=python(c,{mode:'fixtures'}),question='RAG_004中文安全证据 **Markdown** stable evidence',inputs=[['txt',Buffer.from(question),'text/plain'],['md',Buffer.from('# RAG_004\n**第二格式安全资料**'),'text/markdown'],['docx',Buffer.from(f.docx,'base64'),'application/vnd.openxmlformats-officedocument.wordprocessingml.document']];answer.docs=[];
    for(const [ext,bytes,mime]of inputs){const r=await c.upload(`RAG_004-${randomUUID()}.${ext}`,bytes,mime);assert.equal(r.status,201);assert.equal((await c.waitDoc(r.body.document_id,30000)).status,'indexed');answer.docs.push(r.body.document_id);}
    answer.thread=await c.thread('RAG_004独立回答会话');answer.submitted=await c.submit(answer.thread.thread_id,question);answer.run=await c.waitRun(answer.submitted.run_id,30000);answer.events=await c.events(answer.run.run_id);answer.message=(await c.detail(answer.thread.thread_id)).messages.find(x=>x.run_id===answer.run.run_id&&x.role==='assistant');assert.equal(answer.run.status,'succeeded');assert.equal(answer.run.task.state,'succeeded');assert.ok(answer.message);const retrieval=answer.events.find(x=>x.type==='retrieval.completed');assert.ok(retrieval?.data.count>0);assert.equal(retrieval.data.count,retrieval.data.items.length);assert.ok(retrieval.data.items.some(x=>answer.docs.includes(x.document_id)));const first=retrieval.data.items[0],chunk=c.sql(`SELECT text FROM chunks WHERE chunk_id='${first.chunk_id}'`)[0];assert.ok(chunk);assert.ok(answer.message.content.includes(chunk.text.trim()));assert.ok(answer.message.content.startsWith('根据检索到的资料'));const firstDelta=answer.events.find(x=>x.type==='answer.delta');assert.ok(firstDelta.seq>retrieval.seq);return {run_id:answer.run.run_id,documents:answer.docs,retrieval_count:retrieval.data.count,assistant_message_id:answer.message.message_id};
  });
  await s.check('RAG_004','TP-RAG-006','deltas-final','按seq拼接全部answer.delta再strip精确等于最终assistant正文',async()=>{
    assert.ok(answer.message&&answer.events);const deltas=answer.events.filter(x=>x.type==='answer.delta').sort((a,b)=>a.seq-b.seq);assert.ok(deltas.length);assert.equal(deltas.map(x=>x.data.text).join('').trim(),answer.message.content);const completed=answer.events.find(x=>x.type==='message.completed');assert.ok(completed.seq>deltas.at(-1).seq);return {run_id:answer.run.run_id,deltas:deltas.length,characters:[...answer.message.content].length,message_id:answer.message.message_id};
  });
  await s.check('RAG_004','TP-RAG-007','actual-citation-identities','每citation均属于本Run实际召回，Document/Chunk/owner/active/filename/offset/score正确',async()=>{
    assert.ok(answer.message&&answer.events);const evidence=answer.events.find(x=>x.type==='retrieval.completed').data.items,citations=answer.message.citations;assert.equal(citations.length,evidence.length);assert.ok(citations.length);for(const citation of citations){const item=evidence.find(x=>x.chunk_id===citation.chunk_id);assert.ok(item);for(const field of ['document_id','chunk_id','start_offset','end_offset','score'])assert.equal(citation[field],item[field]);const row=c.sql(`SELECT c.document_id,c.index_batch_id,c.start_offset,c.end_offset,d.filename,d.owner_id,d.active_index_batch_id FROM chunks c JOIN documents d ON d.document_id=c.document_id WHERE c.chunk_id='${citation.chunk_id}'`)[0];assert.ok(row);assert.equal(row.owner_id,c.context.owner_id);assert.equal(row.index_batch_id,row.active_index_batch_id);assert.equal(citation.document_id,row.document_id);assert.equal(citation.filename,row.filename);assert.equal(citation.start_offset,row.start_offset);assert.equal(citation.end_offset,row.end_offset);}const completed=answer.events.find(x=>x.type==='message.completed');assert.deepEqual(completed.data.citations,citations);return {run_id:answer.run.run_id,citations:citations.map(x=>({document_id:x.document_id,chunk_id:x.chunk_id,score:x.score})),owner_matches:true};
  });
  let configurations;
  for(const missing of ['model_base_url','model_api_key','model_name','embedding_model_name','all'])await s.check('RAG_005','TP-RAG-009',`missing-${missing}`,'真实Runtime缺任一必填配置明确拒初始化，无静默Mock回退',async()=>{
    configurations??=python(c,{mode:'config'});const result=configurations.missing.find(x=>missing==='all'?x.missing.length===4:x.missing.length===1&&x.missing[0]===missing);assert.ok(result);assert.equal(result.error,'ValueError');return result;
  });
  await s.check('RAG_005','TP-RAG-009','mock-and-configured-real','Mock无外部配置可初始化，完整真实配置选择真实Provider且不发请求',async()=>{configurations??=python(c,{mode:'config'});assert.equal(configurations.mock_embedding,'MockEmbeddingProvider');assert.equal(configurations.mock_model,'MockModelProvider');assert.equal(configurations.real_configured,'OpenAICompatibleProvider');return {mock:true,real_provider:configurations.real_configured,external_requests:0};});
  s.block('RAG_005','TP-RAG-009','container-startup-config','真实模式缺配置容器启动拒绝且安全诊断','已调用真实Runtime初始化；harness固定Mock且不重配生产服务，容器启动配置覆盖待独立驱动。');
  s.block('RAG_006','TP-RAG-010','temporary-http-errors','embed/chat超时/连接失败/500稳定错误分类与有限退避失败','缺少E4隔离本地HTTP协议服务及E2正式Task/Run结算驱动；Python注入异常不能替代真实HTTP协议。');
  s.block('RAG_006','TP-RAG-011','permanent-http-errors','embed/chat401/403/400/不支持模型直接一致failed而不盲重试','缺少E4隔离本地HTTP协议服务及正式永久异常结算驱动，当前通用RUN_FAILED/INDEX_FAILED不能按静态源码冒充正确分类。');
  s.blockCase('RAG_007','缺少E4本地协议服务：逐组畸形JSON/类型/空字段必须通过生产HTTP adapter及handler观察，不能仅检查字段访问源码。');
  s.blockCase('RAG_008','缺少E4分时三片SSE模型替身和Journal时间采样；当前真实adapter请求stream:false风险明确，Mock多delta不是HTTP流协议证据。');
});
