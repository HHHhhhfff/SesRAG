import {documentRagCoverage} from './document-rag-coverage.mjs';
import fs from 'node:fs';
import {randomUUID} from 'node:crypto';
import {runCategory,assert} from '../lib/category-kit.mjs';

export const coveredCases=['CHK_001','CHK_002'];
const driver=fs.readFileSync(new URL('./chk-driver.py',import.meta.url),'utf8');

await runCategory('chk',async s=>{
 await documentRagCoverage(s);
  const c=s.ctx;let result;
  await s.check('CHK_001','TP-CHK-001','pure-character-coverage','每块seq/offset/text精确，首尾覆盖、无空尾块',async()=>{
    result=c.python(driver);for(const sample of result.valid){const text=[...sample.text],rows=sample.chunks;assert.equal(rows[0].start_offset,0);assert.equal(rows.at(-1).end_offset,text.length);for(const [index,row]of rows.entries()){assert.equal(row.seq,index);assert.ok(row.text.length);assert.equal(row.text,text.slice(row.start_offset,row.end_offset).join(''));assert.equal(row.start_offset,index*(sample.size-sample.overlap));assert.equal(row.end_offset,Math.min(row.start_offset+sample.size,text.length));}const coverage=new Set(rows.flatMap(x=>Array.from({length:x.end_offset-x.start_offset},(_,i)=>x.start_offset+i)));assert.equal(coverage.size,text.length);}assert.deepEqual(result.empty,[]);return {parameter_groups:result.valid.length,empty_chunks:0};
  });
  await s.check('CHK_001','TP-CHK-002','pure-overlap','相邻块步长size-overlap且交界重叠字符一致',async()=>{
    assert.ok(result);for(const sample of result.valid){const rows=sample.chunks;for(let i=1;i<rows.length;i++){const prior=[...rows[i-1].text],current=[...rows[i].text];assert.equal(rows[i].start_offset-rows[i-1].start_offset,sample.size-sample.overlap);if(sample.overlap)assert.deepEqual(prior.slice(-sample.overlap),current.slice(0,sample.overlap));else assert.equal(rows[i].start_offset,rows[i-1].end_offset);}}return {parameter_groups:result.valid.length,overlaps:[0,1]};
  });
  const longText='中文🙂ABC '.repeat(300),characters=[...longText];let rows,document;
  await s.check('CHK_001','TP-CHK-001','persisted-default-identity','默认800/120长文生产索引Chunk保存父Document/batch及字符offset',async()=>{
    const r=await c.upload(`CHK_001-${randomUUID()}.txt`,Buffer.from(longText));assert.equal(r.status,201);document=await c.waitDoc(r.body.document_id,30000);assert.equal(document.status,'indexed');rows=c.sql(`SELECT document_id,index_batch_id,seq,text,start_offset,end_offset FROM chunks WHERE document_id='${document.document_id}' ORDER BY seq`);assert.ok(rows.length>=3);for(const [i,row]of rows.entries()){assert.equal(row.seq,i);assert.equal(row.document_id,document.document_id);assert.equal(row.index_batch_id,document.active_index_batch_id);assert.equal(row.text,characters.slice(row.start_offset,row.end_offset).join(''));assert.equal(row.end_offset-row.start_offset,Math.min(800,characters.length-row.start_offset));}assert.equal(rows[0].start_offset,0);assert.equal(rows.at(-1).end_offset,characters.length);return {document_id:document.document_id,batch_id:document.active_index_batch_id,chunks:rows.length,characters:characters.length};
  });
  await s.check('CHK_001','TP-CHK-002','persisted-default-overlap','生产索引相邻Chunk步长680且重叠120字符相同',async()=>{
    assert.ok(rows?.length>=3);for(let i=1;i<rows.length;i++){assert.equal(rows[i].start_offset-rows[i-1].start_offset,680);assert.deepEqual([...rows[i-1].text].slice(-120),[...rows[i].text].slice(0,120));}return {document_id:document.document_id,pairs:rows.length-1,overlap:120};
  });
  for(const [size,overlap]of [[0,0],[-1,0],[4,-1],[4,4],[4,5]])await s.check('CHK_002','TP-CHK-003',`size-${size}-overlap-${overlap}`,'非法切分参数明确ValueError且有界结束',async()=>{
    const value=(result??c.python(driver)).invalid.find(x=>x.size===size&&x.overlap===overlap);assert.ok(value);assert.equal(value.error,'ValueError');return value;
  });
});
