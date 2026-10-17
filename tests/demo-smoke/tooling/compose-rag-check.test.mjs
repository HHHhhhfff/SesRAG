import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import {test} from 'node:test'
import assert from 'node:assert/strict'
import {Context} from '../lib/category-kit.mjs'
import {composeEvidence} from './compose-rag-check.mjs'

test('Compose失败traceback经真实Context落盘仍是可解析且脱敏的JSON',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'sesrag-compose-evidence-'))
 try{
  fs.writeFileSync(path.join(directory,'context.json'),JSON.stringify({run_id:'evidence-test',marker:'sesrag-demo-smoke-v1',compose_project:'sesrag-demo-smoke-evidence'}))
  fs.writeFileSync(path.join(directory,'compose.env'),'SMOKE_PROJECT=sesrag-demo-smoke-evidence\nSMOKE_DB_PASSWORD=synthetic-sensitive-token\n')
  const ctx=new Context({RunId:'evidence-test',RuntimeDir:directory,ArtifactDir:directory})
  const relative=composeEvidence(ctx,'invalid-startup.json',{code:1,timed_out:false,
   stdout:'stdout "quoted" synthetic-sensitive-token',
   stderr:'Traceback:\n  File "/usr/local/lib/python3.12/site-packages/pydantic/main.py", line 1\n  File "C:\\private\\app.py", line 2\nValidationError: "invalid"',
   error:'launch C:\\private\\worker.exe "failure"'})
  const raw=fs.readFileSync(path.join(directory,relative),'utf8')
  const stored=JSON.parse(raw)
  assert.equal(stored.code,1);assert.equal(stored.timed_out,false)
  assert.match(stored.stderr,/ValidationError/);assert.match(stored.stdout,/quoted/)
  assert.ok(!raw.includes('synthetic-sensitive-token'))
  assert.ok(!raw.includes('/usr/local/')&&!raw.includes('private'))
 }finally{fs.rmSync(directory,{recursive:true,force:true})}
})
