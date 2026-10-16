import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { cleanupRegistered } from './cleanup-registered.mjs'
import { processIdentity, sameProcess, stopOwnedProcess } from '../lib/process-identity.mjs'

test('恢复拒绝缺失/复用PID身份，不终止真实对照进程', async () => {
  const child = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { windowsHide: true })
  await once(child, 'spawn')
  try {
    const identity = processIdentity(child.pid)
    assert.throws(() => stopOwnedProcess({ pid: child.pid }), /缺少出生身份/)
    assert.throws(() => stopOwnedProcess({ ...identity, started: 'wrong' }), /PID已复用/)
    assert.ok(processIdentity(child.pid))
  } finally { const closed = once(child, 'close'); child.kill(); await closed }
})

test('真实父进程硬杀后按出生身份回收Chromium并观察退出', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'sesrag-recover-'))
  const ctx = { args: { RuntimeDir: root, RunId: 'recovery-test' }, context: { compose_project: 'sesrag-demo-smoke-recovery' } }
  const url = pathToFileURL(path.resolve('tests/demo-smoke/tooling/frontend-resources.mjs')).href
  const child = spawn(process.execPath, ['--input-type=module', '-e', `import {registeredBrowser} from ${JSON.stringify(url)};await registeredBrowser(${JSON.stringify(ctx)});console.log('ARMED');setInterval(()=>{},1000)`], { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('browser未就绪')), 15000)
      child.stdout.on('data', chunk => { if (chunk.toString().includes('ARMED')) { clearTimeout(timer); resolve() } })
      child.once('exit', () => { clearTimeout(timer); reject(new Error('browser启动进程提前退出')) })
    })
    const registry = JSON.parse(fs.readFileSync(path.join(root, 'frontend-resources.json')))
    const browser = registry.resources.find(row => row.kind === 'browser')
    assert.ok(processIdentity(browser.pid))
    const exited = once(child, 'exit'); child.kill('SIGKILL'); await exited
    const result = cleanupRegistered(root, ctx.args.RunId, ctx.context.compose_project)
    assert.deepEqual(result.errors, [])
    assert.equal(processIdentity(browser.pid), null)
    assert.ok(JSON.parse(fs.readFileSync(path.join(root, 'frontend-resources.json'))).resources.every(row => row.status === 'closed'))
    assert.equal(cleanupRegistered(root, 'wrong', ctx.context.compose_project).status, 'failed')
  } finally {
    if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
    cleanupRegistered(root, ctx.args.RunId, ctx.context.compose_project)
    fs.rmSync(root, { recursive: true })
  }
})

test('PowerShell登记实际启动Node和pwsh身份与独立活跃采样一致，超时后关闭', async () => {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'sesrag-ps-identity-'))
  try {
    for(const command of ['node','pwsh']) {
      const registry=path.join(root,command+'.json')
      const args=command==='node'?"@('-e','setInterval(()=>{},1000)')":"@('-NoProfile','-Command','Start-Sleep -Seconds 30')"
      const script=`. '${path.resolve('tests/demo-smoke/lib/smoke-common.ps1').replaceAll("'","''")}'; $r=Invoke-SmokeProcess '${command}' ${args} 4 '' @{} '${registry.replaceAll("'","''")}' @{run_id='identity-test';project='sesrag-demo-smoke-identity'}; $r.exit_code`
      const parent=spawn('pwsh',['-NoProfile','-Command',script],{windowsHide:true,stdio:['ignore','pipe','pipe']})
      let stdout='',stderr='';parent.stdout.on('data',x=>stdout+=x);parent.stderr.on('data',x=>stderr+=x)
      const closed=once(parent,'close')
      try {
        let row
        const until=Date.now()+5000
        while(Date.now()<until) {
          try {row=JSON.parse(fs.readFileSync(registry)).resources[0]}catch{}
          if(row?.status==='running')break
          await new Promise(resolve=>setTimeout(resolve,20))
        }
        assert.ok(row?.process_identity)
        assert.ok(sameProcess(row.process_identity,processIdentity(row.process_identity.pid)),command+'实际启动路径与独立身份不一致')
        const [code]=await closed;assert.equal(code,0,stderr);assert.equal(stdout.trim(),'124')
        const after=JSON.parse(fs.readFileSync(registry)).resources[0]
        assert.equal(after.status,'closed');assert.equal(after.observed_process_closed,true)
        assert.equal(processIdentity(row.process_identity.pid),null)
      } finally {if(parent.exitCode===null&&parent.signalCode===null){parent.kill();await closed}}
    }
  }finally{fs.rmSync(root,{recursive:true})}
})
