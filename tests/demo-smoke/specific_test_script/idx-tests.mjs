import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {runCategory,assert} from '../lib/category-kit.mjs';

export const coveredCases=['IDX_001','IDX_002','IDX_003','IDX_004','IDX_005','IDX_006','IDX_007'];
const driver=fs.readFileSync(new URL('./idx-driver.py',import.meta.url),'utf8');
const types={txt:'text/plain',md:'text/markdown',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'};

await runCategory('idx',async s=>{
  const c=s.ctx;let data;
  // IDX_001：生产Mock确定性只证明离线流程，不证明真实检索语义。
  await s.check('IDX_001','TP-IDX-001','mock-repeat-finite','同文本同配置向量完全一致、384维且数值有限',async()=>{
    data=c.python(driver);const value=data.vectors;assert.equal(value.equal_repeated,true);assert.deepEqual(value.dimensions,[384,384,384]);assert.equal(value.all_finite,true);for(const norm of value.norms)assert.ok(Math.abs(norm-1)<1e-10);return value;
  });
  // IDX_002：uploaded来自真实上传响应；indexing必须真实采样才算阶段证据。
  for(const ext of ['txt','md','docx'])await s.check('IDX_002','TP-IDX-003',`${ext}-first-index`,'三格式首次Task succeeded、Document indexed、active/Chunk/向量/字符offset完整',async()=>{
    assert.ok(data?.fixtures[ext]);const f=data.fixtures[ext],r=await c.upload(`IDX_002-${randomUUID()}.${ext}`,Buffer.from(f.bytes,'base64'),types[ext]);assert.equal(r.status,201);assert.equal(r.body.status,'uploaded');assert.equal(r.body.active_index_batch_id,null);
    const d=await c.waitDoc(r.body.document_id,30000);assert.equal(d.status,'indexed');assert.equal(d.last_error_code,null);assert.ok(d.active_index_batch_id);
    const tasks=c.sql(`SELECT task_id,state,last_error_code,progress_json FROM tasks WHERE document_id='${d.document_id}'`);assert.equal(tasks.length,1);assert.equal(tasks[0].state,'succeeded');assert.equal(tasks[0].last_error_code,null);assert.equal(tasks[0].progress_json.index_batch_id,d.active_index_batch_id);
    const rows=c.sql(`SELECT document_id,index_batch_id,seq,text,start_offset,end_offset,embedding::text AS vector FROM chunks WHERE document_id='${d.document_id}' ORDER BY seq`);assert.ok(rows.length);for(const [i,row]of rows.entries()){assert.equal(row.document_id,d.document_id);assert.equal(row.index_batch_id,d.active_index_batch_id);assert.equal(row.seq,i);assert.equal(row.text,[...f.text].slice(row.start_offset,row.end_offset).join(''));const vector=JSON.parse(row.vector);assert.equal(vector.length,384);assert.ok(vector.every(Number.isFinite));}assert.equal(rows[0].start_offset,0);assert.equal(rows.at(-1).end_offset,[...f.text].length);
    return {document_id:d.document_id,task_id:tasks[0].task_id,status:d.status,task_state:tasks[0].state,batch_id:d.active_index_batch_id,chunks:rows.length,format:ext};
  });
  s.block('IDX_002','TP-IDX-003','indexing-phase','uploaded→indexing→indexed每阶段有确定步骤证据','上传与终态已真实验证；缺少E2慢Embedding/步骤屏障，快速终态不能倒推indexing阶段。');
  s.blockCase('IDX_003','缺少E2真实领取Task与383/385维Provider受控驱动；默认384向量成功不能证明错维禁止发布。');
  s.block('IDX_004','TP-IDX-004','candidate-inflight','首次/重建候选构建中不可召回且全部成功后才切换','缺少E2多块慢Embedding屏障与独立PG检索采样；不SQL伪造候选状态。');
  s.block('IDX_004','TP-IDX-006','failed-rebuild-old-active','第N块失败回滚候选并保留旧active检索','缺少E2第N块失败Provider与构建期间检索驱动，正常重建成功另DOC_011独立验证。');
  s.block('IDX_005','TP-IDX-005','commit-window','索引active发布与Task成功原子提交','缺少E2两commit之间精确故障驱动；当前两事务风险保留，不能用普通成功终态证明原子性。');
  s.block('IDX_005','TP-IDX-008','ordinary-exhaustion','普通错误重排至上限且Task/Document一致failed','缺少E2重复普通异常驱动，当前retry_waiting回排缺口；PAR_003永久错误不能代替此分支。');
  // IDX_006：仅移动此例精确source至同目录可恢复备份，finally原位恢复。
  await s.check('IDX_006','TP-IDX-009','missing-own-source','本次源文件丢失重建明确失败且Task/Document一致failed、保留旧active',async()=>{
    const r=await c.upload(`IDX_006-${randomUUID()}.txt`,Buffer.from('IDX_006源丢失重建安全资料'));assert.equal(r.status,201);const original=await c.waitDoc(r.body.document_id,30000);assert.equal(original.status,'indexed');
    const saved=c.sql(`SELECT document_id,storage_key,active_index_batch_id FROM documents WHERE document_id='${original.document_id}'`)[0];assert.equal(saved.storage_key,`documents/${saved.document_id}/source.txt`);const backup=`${saved.storage_key}.smoke-${randomUUID()}.backup`;let moved=false,stopped=false;
    const action=operation=>c.python(`import json\nfrom backend.config import Settings\nroot=Settings().upload_path.resolve()\nsource=(root/${JSON.stringify(saved.storage_key)}).resolve()\nbackup=(root/${JSON.stringify(backup)}).resolve()\nassert root in source.parents and root in backup.parents\nassert source.parent==backup.parent\n${operation==='move'?'assert source.is_file() and not backup.exists()\nsource.rename(backup)':'assert backup.is_file() and not source.exists()\nbackup.rename(source)'}\nprint('SMOKE_JSON:'+json.dumps({'operation':${JSON.stringify(operation)},'document_id':${JSON.stringify(saved.document_id)},'source_exists':source.exists(),'backup_exists':backup.exists()}))`);
    try{assert.equal(c.compose(['stop','worker']).code,0);stopped=true;const state=action('move');moved=true;assert.equal(state.source_exists,false);const reindex=await c.request(`/api/v1/documents/${saved.document_id}/index`,{method:'POST'});assert.equal(reindex.status,200);assert.equal(c.compose(['start','worker']).code,0);stopped=false;await c.ready();let timedOut=false;try{await c.waitDoc(saved.document_id,15000);}catch{timedOut=true;}const d=c.sql(`SELECT status,last_error_code,active_index_batch_id FROM documents WHERE document_id='${saved.document_id}'`)[0],t=c.sql(`SELECT state,attempt,max_attempts,last_error_code FROM tasks WHERE task_id='${reindex.body.task_id}'`)[0],rows=c.sql(`SELECT index_batch_id FROM chunks WHERE document_id='${saved.document_id}'`),actual={document_id:saved.document_id,task_id:reindex.body.task_id,document_status:d.status,task_state:t.state,attempt:t.attempt,max_attempts:t.max_attempts,error_code:t.last_error_code,timed_out:timedOut};
      assert.equal(d.active_index_batch_id,saved.active_index_batch_id,JSON.stringify(actual));assert.ok(rows.length&&rows.every(x=>x.index_batch_id===saved.active_index_batch_id),JSON.stringify(actual));assert.equal(d.status,'failed',`源丢失未有界结算：${JSON.stringify(actual)}`);assert.equal(t.state,'failed',JSON.stringify(actual));assert.ok(d.last_error_code&&t.last_error_code);return actual;
    }finally{if(moved)action('restore');if(stopped){assert.equal(c.compose(['start','worker']).code,0);await c.ready();}}
  });
  s.blockCase('IDX_007','缺少E2多块慢Provider与pg_stat_activity确定采样；源码session位置不足以代替长事务实际指标，不擅自增加固定SLO阈值。');
});
