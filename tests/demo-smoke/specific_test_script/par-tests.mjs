import {documentRagCoverage} from './document-rag-coverage.mjs';
import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {runCategory, assert} from '../lib/category-kit.mjs';

export const coveredCases=['PAR_001','PAR_002','PAR_003','PAR_004'];
const driver=fs.readFileSync(new URL('./par-driver.py',import.meta.url),'utf8');
const types={txt:'text/plain',md:'text/markdown',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'};

await runCategory('par',async s=>{
  const c=s.ctx;let data;
  await s.check('PAR_001','TP-PAR-001','production-fixtures','生产Parser读取本次安全三格式生成文件',async()=>{data=c.python(driver);assert.ok(data.txt&&data.md&&data.docx);assert.equal(data.txt.text,data.txt.expected);return {formats:['txt','md','docx'],txt_characters:[...data.txt.text].length};});
  const doc=id=>c.sql(`SELECT document_id,status,active_index_batch_id,last_error_code FROM documents WHERE document_id='${id}'`)[0];
  const task=id=>c.sql(`SELECT task_id,state,attempt,max_attempts,last_error_code FROM tasks WHERE document_id='${id}' ORDER BY created_at DESC`)[0];
  const chunks=id=>c.sql(`SELECT document_id,index_batch_id,seq,text,start_offset,end_offset FROM chunks WHERE document_id='${id}' ORDER BY seq`);
  const upload=async(name,content,ext)=>{const r=await c.upload(`${name}-${randomUUID()}.${ext}`,content,types[ext]);assert.equal(r.status,201);return r.body.document_id;};
  const originals=[];
  // PAR_001：每格式有自己的Document，解析文本与生产Chunk字符范围逐一核对。
  for(const [ext,tp] of [['txt','TP-PAR-001'],['md','TP-PAR-002'],['docx','TP-PAR-003']])await s.check('PAR_001',tp,`${ext}-indexed-text`,'正文字符保真、Markdown保留标记、docx段落换行拼接，Chunk内容与Parser完全一致',async()=>{
    assert.ok(data?.[ext],'生产fixture准备失败');const fixture=data[ext];assert.equal(fixture.text,fixture.expected);assert.equal(fixture.source_name,`${ext}.${ext}`);
    const id=await upload('PAR_001',Buffer.from(fixture.bytes,'base64'),ext),final=await c.waitDoc(id,30000),rows=chunks(id);assert.equal(final.status,'indexed');assert.ok(rows.length);for(const row of rows){assert.equal(row.text,[...fixture.text].slice(row.start_offset,row.end_offset).join(''));assert.equal(row.document_id,id);assert.equal(row.index_batch_id,final.active_index_batch_id);}originals.push({id,fixture,rows});return {document_id:id,format:ext,chunks:rows.length,parsed_characters:[...fixture.text].length};
  });
  await s.check('PAR_001','TP-PAR-007','character-offset','Chunk offset按解析文本Unicode字符并覆盖首尾，不当作字节或页码',async()=>{
    assert.equal(originals.length,3);for(const {fixture,rows} of originals){assert.equal(rows[0].start_offset,0);assert.equal(rows.at(-1).end_offset,[...fixture.text].length);assert.ok(Buffer.byteLength(fixture.text,'utf8')>[...fixture.text].length);}return {documents:originals.map(x=>x.id),offset_unit:'Unicode字符'};
  });
  await s.check('PAR_001','TP-PAR-007','parser-position-contract','统一ParsedDocument具备PRD要求的基础位置字段',async()=>{
    assert.ok(data);assert.ok(['txt','md','docx'].every(ext=>data[ext].position_fields.length>0),'ParsedDocument仅source_name/text，缺少独立基础位置字段');
  });
  // PAR_002：真实损坏上传必须终态结算；retry_waiting/indexing停滞如实failed。
  const damaged=[['bad-txt','txt',Buffer.from([0xff,0xfe,0x80]),'TP-PAR-004'],['bad-md','md',Buffer.from([0xff,0xfe,0x80]),'TP-PAR-004'],['nonzip-docx','docx',Buffer.from('not-a-ZIP'),'TP-PAR-005'],['damaged-zip-docx','docx',Buffer.from([0x50,0x4b,3,4,0,0,0]),'TP-PAR-005']];
  for(const [name,ext,content,tp]of damaged)await s.check('PAR_002',tp,name,'损坏编码/结构最终Document和Task failed，有稳定错误且无active/Chunk',async()=>{
    const id=await upload('PAR_002-'+name,content,ext);let timeout=false;try{await c.waitDoc(id,15000);}catch{timeout=true;}const d=doc(id),t=task(id),rows=chunks(id),actual={document_id:id,document_status:d.status,task_state:t.state,attempt:t.attempt,max_attempts:t.max_attempts,error_code:t.last_error_code,timeout};
    assert.equal(d.active_index_batch_id,null,JSON.stringify(actual));assert.equal(rows.length,0,JSON.stringify(actual));assert.equal(d.status,'failed',`解析错误未结算：${JSON.stringify(actual)}`);assert.equal(t.state,'failed',JSON.stringify(actual));assert.ok(d.last_error_code&&t.last_error_code);return actual;
  });
  // PAR_003：零字节与无段落是真正空文；空白文本只记录当前字符行为。
  const empties=[['zero-txt','txt',Buffer.alloc(0)],['zero-md','md',Buffer.alloc(0)],['empty-docx','docx',data?Buffer.from(data.empty_docx.bytes,'base64'):null]];
  for(const [name,ext,content]of empties){let id;await s.check('PAR_003','TP-PAR-006',name,'真正空解析Document failed且EMPTY_DOCUMENT，无active或候选Chunk',async()=>{
    assert.ok(content,'空docx fixture准备失败');id=await upload('PAR_003-'+name,content,ext);const d=await c.waitDoc(id,30000);assert.equal(d.status,'failed');assert.equal(d.last_error_code,'EMPTY_DOCUMENT');assert.equal(d.active_index_batch_id,null);assert.equal(chunks(id).length,0);return {document_id:id,status:d.status,error_code:d.last_error_code};
  });await s.check('PAR_003','TP-IDX-008',name+'-task','永久空文Task/Document一致failed并且错误码相同',async()=>{assert.ok(id);const d=doc(id),t=task(id);assert.equal(t.state,'failed');assert.equal(t.last_error_code,'EMPTY_DOCUMENT');assert.equal(d.status,t.state);assert.equal(d.last_error_code,t.last_error_code);return {document_id:id,task_id:t.task_id,task_state:t.state,error_code:t.last_error_code};});}
  await s.check('PAR_003','TP-PAR-006','whitespace-observation','空白文本按当前字符切分行为索引，不擅自增加strip规则',async()=>{
    const content=' \n\t ',id=await upload('PAR_003-whitespace',Buffer.from(content),'txt'),d=await c.waitDoc(id,30000),rows=chunks(id);assert.equal(d.status,'indexed');assert.equal(rows.length,1);assert.equal(rows[0].text,content);return {document_id:id,status:d.status,whitespace_characters:content.length};
  });
  for(const name of ['table_only','mixed_regions'])await s.check('PAR_004','TP-PAR-008',name,'明确非段落区域保留结果，table-only按EMPTY_DOCUMENT、混合正文按实际顶层段落索引',async()=>{
    assert.ok(data?.[name]);const f=data[name],id=await upload('PAR_004-'+name,Buffer.from(f.bytes,'base64'),'docx'),d=await c.waitDoc(id,30000),rows=chunks(id);assert.equal(f.text,f.expected);if(name==='table_only'){assert.equal(f.text,'');assert.equal(d.status,'failed');assert.equal(d.last_error_code,'EMPTY_DOCUMENT');assert.equal(rows.length,0);}else{assert.equal(d.status,'indexed');assert.equal(rows.map(x=>x.text).join(''),f.text);assert.equal(f.regions.body,true);}return {document_id:id,status:d.status,retained_regions:f.regions,scope:'当前顶层paragraphs覆盖观察'};
  });
  s.block('PAR_004','TP-PAR-008','full-region-support','明确docx表格/页眉/文本框的产品支持契约','已动态记录各区域是否保留；PRD尚未细化区域范围，当前顶层paragraphs遗漏需需求确认，不能称完整docx区域支持。');
 await documentRagCoverage(s);
});
