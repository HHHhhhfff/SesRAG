import net from 'node:net'
import path from 'node:path'
import { createServer } from 'vite'
import { assert, Context, repoRoot } from '../lib/category-kit.mjs'
import { startControlledWorker } from './pg-execution.mjs'
import { frontendResource, registeredBrowser } from './frontend-resources.mjs'

// FE_003～015：当前前端源码经合法API_PROXY_TARGET连接独立PG控制器。
// TCP网关仅透传字节；关闭监听与现有socket产生真实API不可达，不伪造健康响应。
export async function withFrontendHarness(ctx, fn) {
  const controller = await startControlledWorker(ctx, {}, { frontend: true })
  let vite, browser, gateway, reservation, bodyError
  const sockets = new Set()
  const gatewayRow = frontendResource(ctx, 'api-tcp-relay')
  const viteRow = frontendResource(ctx, 'vite')
  let gatewayPort
  const portRow = frontendResource(ctx, 'vite-port-reservation')
  const upstream = new URL(controller.baseUrl)
  const openGateway = async () => {
    gateway = net.createServer(socket => {
      const remote = net.connect(Number(upstream.port), upstream.hostname)
      for (const item of [socket, remote]) {
        sockets.add(item)
        item.on('error', () => { socket.destroy(); remote.destroy() })
        item.on('close', () => sockets.delete(item))
      }
      socket.pipe(remote).pipe(socket)
    })
    await new Promise((resolve, reject) => { gateway.once('error', reject); gateway.listen(gatewayPort ?? 0, '127.0.0.1', resolve) })
    gatewayPort = gateway.address().port
    gatewayRow.running({ port: gatewayPort })
  }
  const closeGateway = async () => {
    for (const socket of sockets) socket.destroy()
    if (gateway?.listening) await new Promise((resolve, reject) => gateway.close(error => error ? reject(error) : resolve()))
    assert.ok(!gateway?.listening)
  }
  const closeController = async () => {
    try {
      const before = await controller.status()
      if (before.worker_pid) await controller.release()
      const after = before.running ? await controller.stop() : await controller.status()
      ctx.evidence(`fe/controller-${controller.resource.name}.json`, { resource: controller.resource, before, after, observed_worker_exit: !after.running })
      assert.equal(after.running, false)
      if (after.worker_pid) assert.equal(after.exit_code, 0, '本例Worker未正常退出')
    } finally { await controller.close() }
  }
  try {
    await openGateway()
    // Vite将0解释为默认5173；先由OS分配空闲端口再strictPort监听，避免撞开发服务。
    reservation = net.createServer()
    await new Promise((resolve, reject) => { reservation.once('error', reject); reservation.listen(0, '127.0.0.1', resolve) })
    const frontendPort = reservation.address().port
    portRow.running({ port: frontendPort })
    await new Promise(resolve => reservation.close(resolve))
    portRow.closed({ observed_listener_closed: !reservation.listening })
    const previous = process.env.API_PROXY_TARGET
    process.env.API_PROXY_TARGET = `http://127.0.0.1:${gatewayPort}`
    try {
      vite = await createServer({ root: path.join(repoRoot, 'frontend'), configFile: path.join(repoRoot, 'frontend/vite.config.ts'),
        server: { host: '127.0.0.1', port: frontendPort, strictPort: true }, logLevel: 'silent' })
    } finally {
      if (previous === undefined) delete process.env.API_PROXY_TARGET
      else process.env.API_PROXY_TARGET = previous
    }
    await vite.listen()
    const frontendUrl = `http://127.0.0.1:${vite.httpServer.address().port}`
    viteRow.running({ port: vite.httpServer.address().port, proxy_target: controller.baseUrl })
    const api = new Context({ ...ctx.args, BaseUrl: controller.baseUrl, FrontendUrl: frontendUrl })
    browser = await registeredBrowser(ctx)
    return await browser.withPage((page, context) => fn({ controller, api, page, context, frontendUrl, closeGateway, openGateway }))
  } catch(error) { bodyError=error;throw error } finally {
    // 每一级清理失败也继续后续关闭；所有资源归父run，可交5d硬杀恢复。
    const outcomes = []
    for (const [stage,close] of [['browser',() => browser?.close()], ['vite',async () => { await vite?.close(); viteRow.closed({ observed_listener_closed: !vite?.httpServer?.listening }) }],
      ['reservation',async () => { if (reservation?.listening) await new Promise(resolve => reservation.close(resolve)); portRow.closed({ observed_listener_closed: !reservation?.listening }) }],
      ['gateway',async () => { await closeGateway(); gatewayRow.closed({ observed_listener_closed: true, remaining_sockets: sockets.size }) }], ['controller',closeController]]) {
      try { await close() } catch (error) { outcomes.push({stage,error}) }
    }
    if(bodyError||outcomes.length)ctx.evidence(`fe/cleanup-errors-${controller.resource.name}.json`,{body:bodyError?{type:bodyError.name,code:bodyError.code??null,message:bodyError.message}:null,cleanup:outcomes.map(({stage,error})=>({stage,type:error.name,code:error.code??null,message:error.message}))})
    if (outcomes.length) throw new AggregateError([bodyError,...outcomes.map(x=>x.error)].filter(Boolean), ['FE测试资源清理失败',bodyError?.message,...outcomes.map(({stage,error})=>stage+': '+error.message)].filter(Boolean).join('; '))
  }
}
