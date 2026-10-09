import http from 'node:http'
import { fileURLToPath } from 'node:url'
import { createServer as createViteServer } from 'vite'
import { chromium } from 'playwright'

// FE_009前提诊断工具：本地真实HTTP/Vite/Chromium验证空body是否触发open。
// 不连接Compose，不替代产品断言；所有临时server/browser/socket在finally关闭。
const sockets = new Set()
const upstream = http.createServer((request, response) => {
  if (request.url === '/') { response.end('<!doctype html><title>FE_009诊断</title>'); return }
  response.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' })
  if (request.url.includes('flushed-empty')) response.flushHeaders()
  if (request.url.includes('with-frame')) response.write('id: 1\nevent: task.queued\ndata: {"seq":1}\n\n')
})
upstream.on('connection', (socket) => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)) })
let vite
let browser
try {
  await new Promise((resolve) => upstream.listen(0, '127.0.0.1', resolve))
  const upstreamOrigin = `http://127.0.0.1:${upstream.address().port}`
  vite = await createViteServer({ configFile: false, root: fileURLToPath(new URL('../', import.meta.url)), server: { host: '127.0.0.1', port: 0, strictPort: true, proxy: { '/api': upstreamOrigin } }, logLevel: 'silent' })
  await vite.listen()
  const proxyOrigin = `http://127.0.0.1:${vite.httpServer.address().port}`
  browser = await chromium.launch({ headless: true })
  const results = []
  for (const [transport, origin] of [['直接HTTP', upstreamOrigin], ['真实Vite代理', proxyOrigin]]) {
    const context = await browser.newContext()
    try {
      const page = await context.newPage()
      await page.goto(origin, { waitUntil: 'domcontentloaded' })
      for (const mode of ['no-flush-empty', 'flushed-empty', 'with-frame']) {
        const result = await page.evaluate(async (mode) => {
          const source = new EventSource(`/api/${mode}`)
          const observed = { open: false, frame: false, error: false }
          source.addEventListener('open', () => { observed.open = true })
          source.addEventListener('task.queued', () => { observed.frame = true })
          source.addEventListener('error', () => { observed.error = true })
          try { await new Promise((resolve) => setTimeout(resolve, 700)); return observed } finally { source.close() }
        }, mode)
        results.push({ transport, response_mode: mode, ...result })
      }
    } finally { await context.close() }
  }
  process.stdout.write(JSON.stringify({ purpose: 'FE_009工具前提诊断，非产品验收', observations: results }, null, 2) + '\n')
} finally {
  await browser?.close()
  await vite?.close()
  for (const socket of sockets) socket.destroy()
  await new Promise((resolve) => upstream.close(resolve))
}
