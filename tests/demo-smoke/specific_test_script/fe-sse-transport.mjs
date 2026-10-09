import http from 'node:http'
import https from 'node:https'

// FE_009受控传输服务：只透传本用例Run的正式SSE；原始字节不解码、不合成、不改写。
// 只允许本例前端Origin，断线由真实socket.destroy触发，不能调用EventSource.onerror。
export async function createSseRelay({ baseUrl, frontendUrl, runId, lifetimeMs = 45000 }) {
  if (!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(runId)) throw new Error('FE_009透传只接受本用例UUID Run')
  const base = new URL(baseUrl)
  const frontend = new URL(frontendUrl)
  if (!['http:', 'https:'].includes(base.protocol) || !['http:', 'https:'].includes(frontend.protocol) || base.username || base.password || frontend.username || frontend.password) throw new Error('FE_009透传URL无效或包含凭据')
  if (!Number.isInteger(lifetimeMs) || lifetimeMs < 1000 || lifetimeMs > 120000) throw new Error('FE_009透传生命周期必须有界')
  const officialPath = `/api/v1/runs/${runId}/events/stream`
  const allowedOrigin = frontend.origin
  const sockets = new Set()
  const upstreams = new Set()
  const connections = []
  const observedSockets = new Map()
  let closed = false
  const server = http.createServer((request, response) => {
    const input = new URL(request.url ?? '/', 'http://127.0.0.1')
    const cors = { 'Access-Control-Allow-Origin': allowedOrigin, Vary: 'Origin', 'Cache-Control': 'no-store' }
    // FE_009负边界：不代理其他Run/路径/方法/Origin，也不接受任意上游或凭据header。
    if (request.headers.origin !== allowedOrigin || input.pathname !== officialPath || [...input.searchParams.keys()].some((key) => key !== 'after_seq') || (input.searchParams.has('after_seq') && !/^\d+$/.test(input.searchParams.get('after_seq'))) || (request.headers['last-event-id'] && !/^\d+$/.test(String(request.headers['last-event-id'])))) {
      response.writeHead(403); response.end('FE_009传输范围外请求'); return
    }
    if (request.method === 'OPTIONS') {
      const requestedHeaders = String(request.headers['access-control-request-headers'] ?? '').toLowerCase().split(',').map((value) => value.trim()).filter(Boolean)
      if (request.headers['access-control-request-method'] !== 'GET' || requestedHeaders.some((value) => !['last-event-id', 'cache-control'].includes(value))) { response.writeHead(403); response.end(); return }
      response.writeHead(204, { ...cors, 'Access-Control-Allow-Methods': 'GET', 'Access-Control-Allow-Headers': 'Last-Event-ID, Cache-Control' }); response.end(); return
    }
    if (request.method !== 'GET') { response.writeHead(405, cors); response.end(); return }
    const trace = { path: officialPath, after_seq: input.searchParams.get('after_seq'), last_event_id: request.headers['last-event-id'] ?? null, upstream_status: null, forwarded_bytes: 0, closed: false, severed: false }
    connections.push(trace)
    observedSockets.set(request.socket, trace)
    const target = new URL(officialPath + input.search, base)
    const headers = { Accept: 'text/event-stream' }
    if (request.headers['last-event-id']) headers['Last-Event-ID'] = String(request.headers['last-event-id'])
    const upstream = (target.protocol === 'https:' ? https : http).request(target, { method: 'GET', headers, agent: false }, (incoming) => {
      trace.upstream_status = incoming.statusCode ?? 502
      response.writeHead(trace.upstream_status, { ...cors, 'Content-Type': incoming.headers['content-type'] ?? 'text/event-stream' })
      response.flushHeaders()
      incoming.on('data', (bytes) => { trace.forwarded_bytes += bytes.length })
      incoming.on('error', () => { response.destroy() })
      incoming.on('aborted', () => { response.destroy() })
      // pipe处理背压，保留每一个上游字节，包括SSE id/event/data和帧边界。
      incoming.pipe(response)
    })
    upstreams.add(upstream)
    const timer = setTimeout(() => { trace.closed = true; upstream.destroy(); response.destroy() }, lifetimeMs)
    timer.unref()
    upstream.on('error', () => { if (!response.headersSent) response.writeHead(502, cors); response.destroy() })
    upstream.on('close', () => { upstreams.delete(upstream) })
    response.on('close', () => { trace.closed = true; clearTimeout(timer); upstream.destroy(); observedSockets.delete(request.socket) })
    upstream.end()
  })
  server.on('connection', (socket) => { sockets.add(socket); socket.on('close', () => { sockets.delete(socket); observedSockets.delete(socket) }) })
  server.requestTimeout = 10000
  server.headersTimeout = 10000
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', () => { server.off('error', reject); resolve() }) })
  const origin = `http://127.0.0.1:${server.address().port}`
  return {
    origin, officialPath, allowedOrigin, connections,
    url(afterSeq) { return `${origin}${officialPath}${afterSeq === undefined ? '' : `?after_seq=${afterSeq}`}` },
    disconnect() {
      if (closed) throw new Error('FE_009透传服务已关闭')
      let severed = 0
      for (const [socket, trace] of [...observedSockets]) { trace.severed = true; socket.destroy(); severed++ }
      if (!severed) throw new Error('FE_009没有已建立的真实SSE连接可断开')
      return severed
    },
    async close() {
      if (closed) return
      closed = true
      for (const upstream of upstreams) upstream.destroy()
      for (const socket of sockets) socket.destroy()
      // 所有客户端/upstream socket都先关闭，再有界等待server释放监听端口。
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('FE_009透传server关闭超时')), 2000)
        server.close((error) => { clearTimeout(timer); if (error) reject(error); else resolve() })
      })
    },
  }
}
