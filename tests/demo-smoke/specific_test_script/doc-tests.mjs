import {documentRagCoverage} from './document-rag-coverage.mjs';
import fs from 'node:fs';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {runCategory, assert, executeNestedScenario} from '../lib/category-kit.mjs';

export const coveredCases = ['DOC_001','DOC_002','DOC_003','DOC_004','DOC_005','DOC_006','DOC_007','DOC_008','DOC_009','DOC_010','DOC_011'];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const mime = {txt:'text/plain',md:'text/markdown',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'};
const driver = fs.readFileSync(new URL('./doc-driver.py',import.meta.url),'utf8');

await runCategory('doc',async s=>{
  const c=s.ctx, own=[];
  const docx=fs.readFileSync(path.join(c.args.FixtureDir,'upload-safe','smoke.docx'));
  const bytes={txt:Buffer.from('DOC独立安全输入 中文\nsecond line'),md:Buffer.from('# DOC独立资料\n**正文**'),docx};
  const stored=id=>c.sql(`SELECT document_id,owner_id,filename,source,extension,size_bytes,content_hash,storage_key,status,active_index_batch_id,last_error_code,created_at FROM documents WHERE document_id='${id}'`)[0];
  const tasks=id=>c.sql(`SELECT task_id,kind,state,document_id,progress_json,last_error_code FROM tasks WHERE document_id='${id}' ORDER BY created_at`);
  const total=()=>c.sql('SELECT (SELECT count(*) FROM documents) AS documents,(SELECT count(*) FROM tasks) AS tasks')[0];
  const files=()=>c.python(`import json\nfrom backend.config import Settings\np=Settings().upload_path\nprint('SMOKE_JSON:'+json.dumps({'files':sorted(str(x.relative_to(p)) for x in p.rglob('*') if x.is_file())}))`).files;
  const code=r=>r.body?.error?.code ?? r.body?.code;
  const upload=async(name,content,type)=>{const r=await c.upload(name,content,type);if(r.status===201) own.push(r.body.document_id);return r;};
  let paused=false;
  try {
    // DOC_001～DOC_010：暂停本次 Worker，登记断言不借快速索引终态倒推 queued。
    const stop=c.compose(['stop','worker']);assert.equal(stop.code,0,'暂停本次Worker失败');paused=true;
    const registered=[];
    for(const ext of ['txt','md','docx']) await s.check('DOC_001','TP-DOC-001',ext,'三格式登记201且Document和queued索引Task持久关联',async()=>{
      const r=await upload(`DOC_001-${randomUUID()}.${ext}`,bytes[ext],mime[ext]);assert.equal(r.status,201);assert.match(r.body.document_id,uuid);
      const d=stored(r.body.document_id), ts=tasks(d.document_id);registered.push({api:r.body,db:d,bytes:bytes[ext]});
      assert.equal(d.owner_id,c.context.owner_id);assert.equal(d.filename,r.body.filename);assert.equal(d.extension,`.${ext}`);assert.equal(d.size_bytes,bytes[ext].length);
      assert.equal(d.status,'uploaded');assert.equal(d.active_index_batch_id,null);assert.equal(ts.length,1);assert.equal(ts[0].kind,'index_document');assert.equal(ts[0].state,'queued');assert.equal(ts[0].document_id,d.document_id);assert.match(ts[0].progress_json.index_batch_id,uuid);
      assert.equal(d.storage_key,`documents/${d.document_id}/source.${ext}`);assert.ok(Date.parse(r.body.created_at));
      return {document_id:d.document_id,task_id:ts[0].task_id,format:ext,bytes:d.size_bytes,status:d.status};
    });
    await s.check('DOC_001','TP-DOC-006','equal-and-changed-bytes','同字节同hash且独立Document，改变一字节hash不同',async()=>{
      const content=Buffer.from('DOC_001同字节哈希对照A');
      const a=await upload(`DOC_001-a-${randomUUID()}.txt`,content,mime.txt),b=await upload(`DOC_001-b-${randomUUID()}.txt`,content,mime.txt),d=await upload(`DOC_001-c-${randomUUID()}.txt`,Buffer.from('DOC_001同字节哈希对照B'),mime.txt);
      for(const r of [a,b,d]) assert.equal(r.status,201);
      assert.notEqual(a.body.document_id,b.body.document_id);assert.equal(a.body.content_hash,sha(content));assert.equal(a.body.content_hash,b.body.content_hash);assert.notEqual(a.body.content_hash,d.body.content_hash);
      for(const item of registered) assert.equal(item.db.content_hash,sha(item.bytes));
      return {documents:[a.body.document_id,b.body.document_id,d.body.document_id],same_hash:true,changed_hash:true};
    });
    await s.check('DOC_001','TP-DOC-009','owner-list-order','列表仅本owner、创建时间倒序并无存储路径',async()=>{
      const r=await c.request('/api/v1/documents');assert.equal(r.status,200);const list=r.body.documents;
      assert.ok(registered.every(x=>list.some(d=>d.document_id===x.db.document_id)));
      assert.deepEqual(list.map(x=>Date.parse(x.created_at)),list.map(x=>Date.parse(x.created_at)).sort((a,b)=>b-a));
      for(const item of list){assert.equal(stored(item.document_id).owner_id,c.context.owner_id);assert.ok(!('storage_key' in item));assert.ok(!JSON.stringify(item).includes('/data/uploads'));}
      return {count:list.length,registered:registered.length,owner_matches:true};
    });
    await s.check('DOC_001','TP-DOC-001','source-field','Document登记提供PRD要求的独立来源字段',async()=>{
      assert.ok(registered.length>0);for(const item of registered){assert.equal(item.api.source,'local_upload');assert.equal(item.db.source,'local_upload');assert.equal(Date.parse(item.api.created_at),Date.parse(item.db.created_at));}
    });
    // DOC_002：每个白名单/拒绝后缀单独请求，拒绝必须无Document/Task/文件增量。
    for(const ext of ['txt','md','docx','TXT','MD','DOCX','doc','pdf','exe','none']) await s.check('DOC_002','TP-DOC-002',ext,'支持后缀归一接受；非支持后缀415且无副作用',async()=>{
      const allow=['txt','md','docx'].includes(ext.toLowerCase()),before=total(),beforeFiles=files();
      const name=`DOC_002-${randomUUID()}${ext==='none'?'':'.'+ext}`,r=await upload(name,bytes[ext.toLowerCase()]??bytes.txt,mime[ext.toLowerCase()]??mime.txt);
      assert.equal(r.status,allow?201:415);
      if(allow) assert.equal(r.body.extension,'.'+ext.toLowerCase());else{assert.equal(code(r),'UNSUPPORTED_DOCUMENT_TYPE');assert.deepEqual(total(),before);assert.deepEqual(files(),beforeFiles);}
      return {extension:ext,status:r.status,error_code:code(r)??null};
    });
    // DOC_003：接受边界用生产函数savepoint隔离，超限仍通过真实HTTP拒绝。
    await s.check('DOC_003','TP-DOC-003','production-exact-10mib','生产登记函数恰10MiB持久化元数据和原文件，回滚后无队列污染',async()=>{
      const r=c.python(driver,{timeoutMs:30000});assert.equal(r.size,10*1024*1024);assert.equal(r.stored_size,r.size);assert.equal(r.hash,r.expected_hash);assert.equal(r.document_status,'uploaded');assert.equal(r.task_state,'queued');assert.equal(r.task_kind,'index_document');assert.ok(r.task_document&&r.batch_present&&r.rollback_document_absent&&r.rollback_task_absent);return r;
    });
    await s.check('DOC_003','TP-DOC-003','http-plus-one','HTTP上传10MiB+1拒413且无文件/Document/Task副作用',async()=>{
      const before=total(),beforeFiles=files(),r=await upload(`DOC_003-${randomUUID()}.txt`,Buffer.alloc(10*1024*1024+1,97),mime.txt);
      assert.equal(r.status,413);assert.equal(code(r),'DOCUMENT_TOO_LARGE');assert.deepEqual(total(),before);assert.deepEqual(files(),beforeFiles);return {bytes:10*1024*1024+1,status:r.status,error_code:code(r)};
    });
    await s.check('DOC_003','TP-DOC-003','http-exact-10mib','独立场景真实HTTP恰10MiB接受，原文件/大小/hash/queued Task准确且完整清理',async()=>{
      const nested=await executeNestedScenario(c,'doc-limit');assert.equal(nested.summary.status,'passed');assert.equal(nested.cleanup.status,'passed');assert.ok(nested.report);assert.equal(nested.report.category,'doc-limit');assert.equal(nested.report.status,'passed');const target=nested.report.checks.find(x=>x.id==='DOC_003__TP-DOC-003__http-exact-10mib');assert.ok(target);assert.equal(target.status,'passed');const actual=typeof target.actual==='string'?JSON.parse(target.actual):target.actual;assert.equal(actual.status,201);assert.equal(actual.bytes,10*1024*1024);assert.equal(actual.stored_bytes,actual.bytes);assert.equal(actual.exact_saved_bytes,true);assert.equal(actual.document_status,'uploaded');assert.equal(actual.task_state,'queued');assert.match(actual.content_hash,/^[0-9a-f]{64}$/);assert.ok(actual.document_id&&actual.task_id);assert.ok(nested.report.checks.length&&nested.report.checks.every(x=>x.status==='passed'));return {scenario:'doc-limit',nested_run_id:nested.report.run_id,checks:nested.report.checks.map(x=>({id:x.id,status:x.status})),bytes:actual.bytes,status:actual.status,cleanup:nested.cleanup.status,evidence:'evidence/nested/doc-limit-summary.json'};
    });
    // DOC_004：无MIME使用真实multipart字节，避免Blob自动补octet-stream掩盖该分支。
    for(const ext of ['txt','md','docx']) for(const type of [mime[ext],...(ext==='md'?['text/plain']:[]),'application/octet-stream',null,'image/png']) await s.check('DOC_004','TP-DOC-004',`${ext}-${type??'none'}`.replaceAll('/','-'),'允许MIME/未指定接受，不匹配415且无副作用',async()=>{
      const before=total(),beforeFiles=files();let r;
      if(type===null){const boundary=`smoke-${randomUUID()}`,name=`DOC_004-${randomUUID()}.${ext}`,body=Buffer.concat([Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${name}"\r\n\r\n`),bytes[ext],Buffer.from(`\r\n--${boundary}--\r\n`)]);const response=await fetch(new URL('/api/v1/documents',c.args.BaseUrl),{method:'POST',headers:{'Content-Type':`multipart/form-data; boundary=${boundary}`},body,signal:AbortSignal.timeout(10000)});r={status:response.status,body:await response.json()};if(r.status===201)own.push(r.body.document_id);}
      else r=await upload(`DOC_004-${randomUUID()}.${ext}`,bytes[ext],type);
      assert.equal(r.status,type==='image/png'?415:201);if(type==='image/png'){assert.equal(code(r),'DOCUMENT_MIME_MISMATCH');assert.deepEqual(total(),before);assert.deepEqual(files(),beforeFiles);}return {format:ext,mime:type,status:r.status,error_code:code(r)??null};
    });
    await s.check('DOC_005','TP-DOC-005','production-sentinel','生产登记函数路径名/绝对样式/Unicode原名不能覆盖旁路哨兵',async()=>{
      const result=c.python(driver,{timeoutMs:30000});assert.equal(result.sentinel_checks.length,3);assert.ok(result.sentinel_checks.every(x=>x.server_uuid_key&&x.under_upload_root&&x.sentinel_unchanged));return {variants:3,sentinel_unchanged:true,scope:'本用例独立临时上传范围和PG保存点'};
    });
    for(const filename of ['../sentinel.txt','/absolute/sentinel.txt','C:\\absolute\\sentinel.txt','中文 ☃ 特殊&.txt']) await s.check('DOC_005','TP-DOC-005',sha(filename).slice(0,8),'原名不控制服务端UUID路径，已保存文件身份与内容匹配',async()=>{
      const content=Buffer.from('DOC_005安全路径哨兵'),r=await upload(filename,content,mime.txt);assert.equal(r.status,201);const d=stored(r.body.document_id);assert.equal(r.body.filename,filename==='中文 ☃ 特殊&.txt'?filename:'sentinel.txt');assert.equal(d.filename,r.body.filename);assert.equal(d.storage_key,`documents/${d.document_id}/source.txt`);
      const state=c.python(`import hashlib,json\nfrom backend.config import Settings\nroot=Settings().upload_path.resolve()\nkey=${JSON.stringify(d.storage_key)}\np=(root/key).resolve()\nprint('SMOKE_JSON:'+json.dumps({'under_root':root in p.parents,'hash':hashlib.sha256(p.read_bytes()).hexdigest(),'relative_matches':str(p.relative_to(root))==key}))`);assert.ok(state.under_root&&state.relative_matches);assert.equal(state.hash,sha(content));assert.ok(!JSON.stringify(r.body).includes('/data/uploads'));return {document_id:d.document_id,status:r.status,under_uuid_path:true};
    });
    // DOC_005：真实浏览器显示API原名，Vue插值不得执行原名中的HTML事件。
    await s.check('DOC_005','TP-DOC-005','browser-filename-text','API登记原名在真实文档列表作为纯文本显示，不执行HTML/事件',async()=>{
      const filenames=[`DOC_005-${randomUUID()}-中文 ☃ &.txt`,`DOC_005-${randomUUID()}-<img src=x onerror=globalThis.__doc005Executed=true>.txt`],documents=[];
      for(const filename of filenames){const r=await upload(filename,Buffer.from('DOC_005浏览器独立安全资料'),mime.txt);assert.equal(r.status,201);documents.push(r.body);}
      const {chromium}=await import('playwright');let browser;
      try{browser=await chromium.launch({headless:true});const page=await browser.newPage();await page.addInitScript(()=>{globalThis.__doc005Executed=false;});const dialogs=[];page.on('dialog',async dialog=>{dialogs.push(dialog.type());await dialog.dismiss();});await page.goto(c.args.FrontendUrl,{waitUntil:'networkidle',timeout:30000});
        for(const document of documents){const label=page.getByText(document.filename,{exact:true});await label.waitFor({state:'visible',timeout:15000});assert.equal(await label.textContent(),document.filename);assert.equal(await label.locator('img,svg,script,iframe').count(),0);}
        assert.equal(await page.evaluate(()=>globalThis.__doc005Executed),false);assert.deepEqual(dialogs,[]);return {documents:documents.map(x=>x.document_id),displayed_exactly:true,html_elements_created:0,events_executed:false};
      }finally{await browser?.close();}
    });
    await s.check('DOC_005','TP-DOC-005','long-name-observation','超长文件名观察按API实际处理，拒绝无副作用且响应可诊断不泄漏路径',async()=>{
      const filename=`DOC_005-${randomUUID()}-${'长'.repeat(300)}.txt`,before=total(),beforeFiles=files(),r=await upload(filename,Buffer.from('DOC_005超长名安全资料'),mime.txt),response=JSON.stringify(r.body);
      assert.ok(!/\/data\/uploads|Traceback|sqlalchemy|psycopg|[A-Za-z]:\\|storage_key/i.test(response),'超长名错误泄漏路径/堆栈/持久化内部信息');
      assert.equal(r.status,422);assert.equal(code(r),'INVALID_DOCUMENT_FILENAME');
      assert.ok(r.status>=400&&r.status<600);assert.deepEqual(total(),before);assert.deepEqual(files(),beforeFiles);assert.ok(code(r)&&typeof r.body?.message==='string','超长名拒绝仅通用错误，缺少可诊断稳定错误码/安全说明');return {filename_characters:[...filename].length,status:r.status,error_code:code(r),rejection_safe:true};
    });
    await s.check('DOC_008','TP-DOC-010','queued','queued重复index返回同Task且无新batch',async()=>{
      const r=await upload(`DOC_008-${randomUUID()}.txt`,bytes.txt,mime.txt);assert.equal(r.status,201);const id=r.body.document_id,before=tasks(id);assert.equal(before[0].state,'queued');
      const a=await c.request(`/api/v1/documents/${id}/index`,{method:'POST'}),b=await c.request(`/api/v1/documents/${id}/index`,{method:'POST'});assert.equal(a.status,200);assert.equal(b.status,200);assert.equal(a.body.task_id,before[0].task_id);assert.equal(b.body.task_id,a.body.task_id);assert.deepEqual(tasks(id),before);return {document_id:id,task_id:a.body.task_id,state:'queued'};
    });
    await s.check('DOC_010','TP-DOC-012','missing-document','不存在Document索引404且无Task/文件副作用',async()=>{
      const before=total(),beforeFiles=files(),id=randomUUID(),r=await c.request(`/api/v1/documents/${id}/index`,{method:'POST'});assert.equal(r.status,404);assert.equal(code(r),'DOCUMENT_NOT_FOUND');assert.deepEqual(total(),before);assert.deepEqual(files(),beforeFiles);return {document_id:id,status:r.status,error_code:code(r)};
    });
  } finally {
    if(paused){const restart=c.compose(['start','worker']);assert.equal(restart.code,0,'恢复本次Worker失败');await c.ready();}
  }
  // DOC_009/DOC_011：每例单独先索引，再暂停Worker使新请求的queued身份可读。
  for(let round=1;round<=3;round++)await s.check('DOC_009','TP-DOC-011',`ordinary-concurrency-${round}`,'普通并发重建只产生一个活动Task并且顺序请求不报多行错误',async()=>{
    const r=await upload(`DOC_009-${randomUUID()}.txt`,bytes.txt,mime.txt);assert.equal(r.status,201);await c.waitDoc(r.body.document_id,30000);let stopped=false;
    try{assert.equal(c.compose(['stop','worker']).code,0);stopped=true;const id=r.body.document_id,responses=await Promise.all([0,1].map(()=>c.request(`/api/v1/documents/${id}/index`,{method:'POST'})));for(const x of responses)assert.equal(x.status,200);const active=tasks(id).filter(t=>['queued','leased','running','retry_waiting'].includes(t.state));assert.equal(active.length,1,'普通并发创建了重复活动索引Task');assert.equal(responses[0].body.task_id,responses[1].body.task_id);const repeat=await c.request(`/api/v1/documents/${id}/index`,{method:'POST'});assert.equal(repeat.status,200);assert.equal(repeat.body.task_id,active[0].task_id);return {document_id:id,active_tasks:active.length,task_id:active[0].task_id};}
    finally{if(stopped){assert.equal(c.compose(['start','worker']).code,0);await c.ready();}}
  });
  const rebuild={};
  await s.check('DOC_011','TP-DOC-013','terminal-rebuild','indexed/failed终态都创建新Task和batch，queued保留旧active',async()=>{
    const good=await upload(`DOC_011-${randomUUID()}.txt`,Buffer.from('DOC_011历史引用资料'),mime.txt),empty=await upload(`DOC_011-empty-${randomUUID()}.txt`,Buffer.alloc(0),mime.txt);assert.equal(good.status,201);assert.equal(empty.status,201);await c.waitDoc(good.body.document_id,30000);await c.waitDoc(empty.body.document_id,30000);
    const thread=await c.thread('DOC_011独立历史引用'),run=await c.submit(thread.thread_id,'DOC_011历史引用资料');await c.waitRun(run.run_id,30000);const detail=await c.detail(thread.thread_id);rebuild.history=detail.messages.find(x=>x.run_id===run.run_id&&x.role==='assistant');assert.ok(rebuild.history);assert.ok(rebuild.history.citations.some(x=>x.document_id===good.body.document_id),'历史回答必须实际引用本例待重建文档');rebuild.thread=thread.thread_id;
    let stopped=false;try{assert.equal(c.compose(['stop','worker']).code,0);stopped=true;rebuild.docs=[];for(const id of [good.body.document_id,empty.body.document_id]){const before=stored(id),old=tasks(id);assert.ok(['indexed','failed'].includes(before.status));const r=await c.request(`/api/v1/documents/${id}/index`,{method:'POST'});assert.equal(r.status,200);const after=stored(id),ts=tasks(id);assert.equal(ts.length,old.length+1);assert.ok(!old.some(x=>x.task_id===r.body.task_id));assert.equal(after.status,'uploaded');assert.equal(after.active_index_batch_id,before.active_index_batch_id);const fresh=ts.find(x=>x.task_id===r.body.task_id);assert.ok(!old.some(x=>x.progress_json.index_batch_id===fresh.progress_json.index_batch_id));rebuild.docs.push({id,old_batch:before.active_index_batch_id,new_batch:fresh.progress_json.index_batch_id,old_status:before.status});}return {documents:rebuild.docs.map(x=>({document_id:x.id,prior_status:x.old_status})),new_tasks:true};}
    finally{if(stopped){assert.equal(c.compose(['start','worker']).code,0);await c.ready();}}
  });
  await s.check('DOC_011','TP-IDX-007','replace-and-preserve-history','重建成功只保留新batch/seq唯一且历史Message引用不改，空文再次failed',async()=>{
    assert.ok(rebuild.docs?.length===2,'重建前置数据未成功创建');for(const x of rebuild.docs){const d=await c.waitDoc(x.id,30000);assert.equal(d.status,x.old_status==='indexed'?'indexed':'failed');const chunks=c.sql(`SELECT index_batch_id,seq FROM chunks WHERE document_id='${x.id}'`);if(x.old_status==='indexed'){assert.equal(d.active_index_batch_id,x.new_batch);assert.ok(chunks.length);assert.ok(chunks.every(y=>y.index_batch_id===x.new_batch));assert.equal(new Set(chunks.map(y=>y.seq)).size,chunks.length);}else{assert.equal(d.last_error_code,'EMPTY_DOCUMENT');assert.equal(chunks.length,0);}}
    const history=(await c.detail(rebuild.thread)).messages.find(x=>x.message_id===rebuild.history.message_id);assert.deepEqual(history,rebuild.history);return {documents:rebuild.docs.map(x=>x.id),historical_message:history.message_id,history_unchanged:true};
  });
 await documentRagCoverage(s);
});
