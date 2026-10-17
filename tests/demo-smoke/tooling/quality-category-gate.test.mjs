import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import {test} from 'node:test'
import assert from 'node:assert/strict'
import {categoryGate} from '../lib/quality-category-gate.mjs'
import {readCases} from '../lib/category-kit.mjs'

test('完整分类拒绝漏TP、非约定blocked、missing证据和伪总状态',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sesrag-quality-gate-'))
 const ctx={args:{ArtifactDir:dir,RunId:'gate-run'}}
 const checks=[...readCases()].filter(([id])=>id.startsWith('CHK_')).flatMap(([id,row])=>row.points.map(tp=>({id:id+'__'+tp+'__matrix',test_point_id:tp,status:'passed',expected:'工具检查',actual:'通过',evidence:[]})))
 const report={schema_version:1,run_id:'gate-run',category:'chk',status:'passed',started_at:'2026-10-13T00:00:00Z',finished_at:'2026-10-13T00:00:01Z',checks,evidence:[]}
 const write=value=>fs.writeFileSync(path.join(dir,'categories/chk.json'),JSON.stringify(value))
 try{
  fs.mkdirSync(path.join(dir,'categories'));write(report)
  assert.equal((await categoryGate(ctx,'chk',[checks[0].id])).checks,checks.length)
  write({...report,checks:checks.slice(0,-1)});await assert.rejects(categoryGate(ctx,'chk',[checks[0].id]),/缺少完整分类/)
  write({...report,status:'blocked',checks:checks.map((row,i)=>i===checks.length-1?{...row,status:'blocked'}:row)});await assert.rejects(categoryGate(ctx,'chk',[checks[0].id]),/未约定/)
  write({...report,checks:checks.map((row,i)=>i?row:{...row,evidence:['missing.json']})});await assert.rejects(categoryGate(ctx,'chk',[checks[0].id]),/证据不存在/)
  write({...report,status:'failed'});await assert.rejects(categoryGate(ctx,'chk',[checks[0].id]),/状态与逐项/)
 }finally{fs.rmSync(dir,{recursive:true})}
})
