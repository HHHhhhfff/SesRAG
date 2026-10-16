import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { spawn } from 'node:child_process'
import { pathToFileURL } from 'node:url'
import { frontendResource, registeredFrontendProcess, registeredBrowser } from './frontend-resources.mjs'
import { processIdentity, sameProcess, stopOwnedProcess } from '../lib/process-identity.mjs'

// LIFE_006工具负哨兵：本机临时目录仅存登记，不访问业务库或主环境。
function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sesrag-fe-resource-'))
  const ctx = { args: { RuntimeDir: root, RunId: 'frontend-resource-test' }, context: { compose_project: 'sesrag-demo-smoke-resource-test' } }
  return { ctx, close: () => fs.rmSync(root, { recursive: true }), rows: () => JSON.parse(fs.readFileSync(path.join(root, 'frontend-resources.json'))).resources }
}

test('其他run登记不可被覆盖', () => {
  const f = fixture()
  try {
    frontendResource(f.ctx, 'probe').closed({ never_started: true })
    assert.throws(() => frontendResource({ ...f.ctx, args: { ...f.ctx.args, RunId: 'other' } }, 'probe'))
    assert.equal(f.rows().length, 1)
  } finally { f.close() }
})

test('Node活跃登记写失败可await捕获并finally，真实子进程关闭且原错保留', async () => {
  const f=fixture(), url=pathToFileURL(path.resolve('tests/demo-smoke/tooling/frontend-resources.mjs')).href
  let identity
  try {
    const source=`import fs from 'node:fs';import {registeredFrontendProcess} from ${JSON.stringify(url)};
const rename=fs.renameSync;let count=0;fs.renameSync=(...args)=>{if(++count===2)throw Object.assign(new Error('NODE_REGISTER_SENTINEL'),{code:'EIO'});return rename(...args)};
try{await registeredFrontendProcess(${JSON.stringify(f.ctx)},process.execPath,['-e','setTimeout(()=>{},8000)']);console.log('UNEXPECTED_SUCCESS')}catch(error){console.log('CAUGHT:'+error.message+':'+error.code)}finally{console.log('CALLER_FINALLY')}`
    const child=spawn(process.execPath,['--input-type=module','-e',source],{windowsHide:true,stdio:['ignore','pipe','pipe']})
    let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x)
    const timer=setTimeout(()=>child.kill(),15000)
    const code=await new Promise(resolve=>child.on('close',resolve));clearTimeout(timer)
    const pending=path.join(f.ctx.args.RuntimeDir,'frontend-resources.json.tmp')
    if(fs.existsSync(pending))identity=JSON.parse(fs.readFileSync(pending)).resources[0].process_identity
    identity??=f.rows()[0].process_identity
    assert.equal(code,0,stderr)
    assert.match(stdout,/CAUGHT:NODE_REGISTER_SENTINEL:EIO/)
    assert.match(stdout,/CALLER_FINALLY/)
    assert.equal(f.rows()[0].status,'closed')
    if(identity)assert.equal(sameProcess(identity,processIdentity(identity.pid)),false)
  }finally{if(identity&&sameProcess(identity,processIdentity(identity.pid)))stopOwnedProcess(identity);f.close()}
})

test('Node启动失败可捕获原ENOENT，快速退出保留真实7且closed', async () => {
  const f=fixture()
  try {
    await assert.rejects(registeredFrontendProcess(f.ctx,'sesrag-no-such-executable-sentinel',[]),error=>error.code==='ENOENT')
    for(let i=0;i<10;i++)assert.equal((await registeredFrontendProcess(f.ctx,process.execPath,['-e','process.exit(7)'])).code,7)
    assert.equal(f.rows().length,11)
    assert.ok(f.rows().every(row=>row.status==='closed'&&row.observed_process_closed))
  }finally{f.close()}
})

test('非零退出不能变成通过，PID真实退出后才closed', async () => {
  const f = fixture()
  try {
    const result = await registeredFrontendProcess(f.ctx, process.execPath, ['-e', 'process.exit(7)'])
    assert.equal(result.code, 7)
    assert.equal(f.rows()[0].status, 'closed')
    assert.ok(f.rows()[0].pid > 0)
    assert.throws(() => process.kill(f.rows()[0].pid, 0))
  } finally { f.close() }
})

test('有界超时终止自己的进程树并观察退出', async () => {
  const f = fixture()
  try {
    const grandchild = "console.log('GRANDCHILD:'+process.pid);setInterval(()=>{},1000)"
    const child = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(grandchild)}],{stdio:'inherit',windowsHide:true});console.log('CHILD:'+process.pid);setInterval(()=>{},1000)`
    const parent = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(child)}],{stdio:'inherit',windowsHide:true});setInterval(()=>{},1000)`
    const result = await registeredFrontendProcess(f.ctx, process.execPath, ['-e', parent], { timeoutMs: 1500 })
    assert.equal(result.code, 124)
    assert.equal(result.timed_out, true)
    assert.equal(f.rows()[0].status, 'closed')
    assert.throws(() => process.kill(f.rows()[0].pid, 0))
    for (const label of ['CHILD', 'GRANDCHILD']) {
      const pid = Number(result.stdout.match(new RegExp(label+':(\\d+)'))?.[1])
      assert.ok(pid > 0, '必须实际启动持有管道的子孙进程')
      assert.throws(() => process.kill(pid, 0))
    }
  } finally { f.close() }
})

test('browser.close异常仍关闭真实Chromium服务器并保留异常', async () => {
  const f = fixture()
  let registered, original
  try {
    registered = await registeredBrowser(f.ctx)
    original = registered.browser.close.bind(registered.browser)
    registered.browser.close = async () => { throw new Error('close-sentinel') }
    await assert.rejects(registered.close(), /close-sentinel/)
    const row = f.rows().find(item => item.kind === 'browser')
    assert.equal(row.status, 'closed')
    assert.throws(() => process.kill(row.pid, 0))
    assert.equal(registered.browser.isConnected(), false)
  } finally {
    if (registered) { registered.browser.close = original; await registered.close().catch(() => {}) }
    f.close()
  }
})

test('QLT父进程和FE子进程并发登记不丢行、不共享临时文件', async () => {
  const f=fixture()
  const url=pathToFileURL(path.resolve('tests/demo-smoke/tooling/frontend-resources.mjs')).href
  const at=Date.now()+3500
  try {
    const results=await Promise.all(Array.from({length:4},()=>new Promise(resolve=>{
      const source=`import {frontendResource} from ${JSON.stringify(url)};while(Date.now()<${at})Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,10);for(let i=0;i<20;i++)frontendResource(${JSON.stringify(f.ctx)},'concurrent-probe').closed({observed:true});`
      const child=spawn(process.execPath,['--input-type=module','-e',source],{windowsHide:true,stdio:['ignore','pipe','pipe']})
      let stderr='';child.stderr.on('data',x=>stderr+=x);child.on('close',code=>resolve({code,stderr}))
    })))
    assert.ok(results.every(row=>row.code===0),JSON.stringify(results))
    assert.equal(f.rows().length,80)
    assert.equal(new Set(f.rows().map(row=>row.id)).size,80)
  } finally { f.close() }
})

test('登记异常释放锁且遗留锁只等待有界5秒', () => {
  const f=fixture(), lock=path.join(f.ctx.args.RuntimeDir,'frontend-resources.json.lock')
  try {
    frontendResource(f.ctx,'probe').closed()
    assert.throws(()=>frontendResource({...f.ctx,args:{...f.ctx.args,RunId:'wrong'}},'rejected'))
    assert.equal(fs.existsSync(lock),false)
    fs.writeFileSync(lock,'owned-test-lock')
    const start=performance.now()
    assert.throws(()=>frontendResource(f.ctx,'blocked'),error=>error.code==='EEXIST')
    const elapsed=performance.now()-start
    assert.ok(elapsed>=4900&&elapsed<6500)
    assert.equal(f.rows().length,1)
  }finally{f.close()}
})

test('登记原子替换瞬态EPERM重试，永久占用保留原事实及pending并释放锁', () => {
  const f=fixture(), original=fs.renameSync
  const file=path.join(f.ctx.args.RuntimeDir,'frontend-resources.json')
  try {
    const resource=frontendResource(f.ctx,'rename-probe')
    let attempts=0
    fs.renameSync=(...args)=>{if(++attempts<=2)throw Object.assign(new Error('rename sharing sentinel'),{code:'EPERM'});return original(...args)}
    resource.running({observed:true})
    assert.equal(attempts,3)
    assert.equal(f.rows()[0].status,'running')
    fs.renameSync=()=>{throw Object.assign(new Error('rename permanent sentinel'),{code:'EPERM'})}
    const started=performance.now()
    assert.throws(()=>resource.closed(),/rename permanent sentinel/)
    const elapsed=performance.now()-started
    assert.ok(elapsed>=4900&&elapsed<6500)
    assert.equal(f.rows()[0].status,'running')
    assert.equal(JSON.parse(fs.readFileSync(file+'.tmp')).resources[0].status,'closed')
    assert.equal(fs.existsSync(file+'.lock'),false)
  }finally{fs.renameSync=original;f.close()}
})
