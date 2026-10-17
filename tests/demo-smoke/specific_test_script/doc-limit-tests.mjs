import {createHash,randomUUID} from 'node:crypto';
import {runCategory,assert} from '../lib/category-kit.mjs';

export const coveredCases=['DOC_003'];

await runCategory('doc-limit',async s=>{
  const c=s.ctx;
  // DOC_003：专属环境仅验证登记；accepted大文件不进入Worker切片，销毁归总入口。
  await s.check('DOC_003','TP-DOC-003','http-exact-10mib','真实HTTP恰10MiB UTF8文本登记201，原字节保存、元数据/hash/queued Task准确',async()=>{
    assert.match(c.context.compose_project,/^sesrag-demo-smoke-doc-limit-[a-z0-9]+$/,'限额场景只能使用总入口专属project');assert.equal(c.sql('SELECT count(*) AS documents FROM documents')[0].documents,0);assert.equal(c.sql('SELECT count(*) AS chunks FROM chunks')[0].chunks,0);
    const stop=c.compose(['stop','worker']);assert.equal(stop.code,0,'独立限额场景Worker暂停失败');const size=10*1024*1024,bytes=Buffer.alloc(size,32),hash=createHash('sha256').update(bytes).digest('hex'),filename=`DOC_003-${randomUUID()}.txt`,r=await c.upload(filename,bytes,'text/plain');assert.equal(r.status,201);assert.equal(r.body.filename,filename);assert.equal(r.body.extension,'.txt');assert.equal(r.body.size_bytes,size);assert.equal(r.body.content_hash,hash);assert.equal(r.body.status,'uploaded');assert.equal(r.body.active_index_batch_id,null);
    const d=c.sql(`SELECT document_id,owner_id,filename,extension,size_bytes,content_hash,storage_key,status,active_index_batch_id FROM documents WHERE document_id='${r.body.document_id}'`)[0];assert.equal(d.owner_id,c.context.owner_id);assert.equal(d.filename,filename);assert.equal(d.extension,'.txt');assert.equal(d.size_bytes,size);assert.equal(d.content_hash,hash);assert.equal(d.status,'uploaded');assert.equal(d.active_index_batch_id,null);assert.equal(d.storage_key,`documents/${d.document_id}/source.txt`);
    const t=c.sql(`SELECT task_id,document_id,kind,state,progress_json FROM tasks WHERE document_id='${d.document_id}'`);assert.equal(t.length,1);assert.equal(t[0].document_id,d.document_id);assert.equal(t[0].kind,'index_document');assert.equal(t[0].state,'queued');assert.ok(t[0].progress_json.index_batch_id);
    const saved=c.python(`import hashlib,json\nfrom backend.config import Settings\nroot=Settings().upload_path.resolve()\nsource=(root/${JSON.stringify(d.storage_key)}).resolve()\nassert root in source.parents\nraw=source.read_bytes()\nprint('SMOKE_JSON:'+json.dumps({'size':len(raw),'hash':hashlib.sha256(raw).hexdigest(),'utf8_characters':len(raw.decode('utf-8')),'exact_spaces':raw==b' '*${size},'temporary_exists':source.with_suffix(source.suffix+'.tmp').exists()}))`);assert.equal(saved.size,size);assert.equal(saved.hash,hash);assert.equal(saved.utf8_characters,size);assert.equal(saved.exact_spaces,true);assert.equal(saved.temporary_exists,false);assert.equal(c.sql(`SELECT count(*) AS chunks FROM chunks WHERE document_id='${d.document_id}'`)[0].chunks,0);
    return {document_id:d.document_id,task_id:t[0].task_id,bytes:size,status:r.status,document_status:d.status,task_state:t[0].state,content_hash:hash,stored_bytes:saved.size,exact_saved_bytes:true,worker_paused_until_runner_cleanup:true};
  });
});
