const configuredBase = (import.meta.env.VITE_API_BASE_URL ?? '').trim()
const baseUrl = (() => {
  if (!configuredBase) return ''
  const url = new URL(configuredBase)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('API 地址只能是无凭据的 HTTP(S) origin')
  return url.origin
})()

export function apiUrl(path: string) { return `${baseUrl}${path}` }
export function safeErrorCode(value: unknown): string {
  return typeof value === 'string' && /^[A-Z][A-Z0-9_]{0,79}$/.test(value) ? value : 'REQUEST_FAILED'
}

export class ApiError extends Error {
  readonly code: string
  constructor(code: unknown, status: number) {
    const safeCode = safeErrorCode(code)
    super(`${safeCode}：请求失败（${status}）`)
    this.code = safeCode
  }
}

export function failureCode(cause: unknown, fallback: string): string {
  return cause instanceof ApiError ? cause.code : cause instanceof Error && /^[A-Z][A-Z0-9_]{0,79}$/.test(cause.message) ? cause.message : fallback
}

export async function apiFetch<T>(path: string, init?: RequestInit, acceptedStatuses: number[] = []): Promise<T> {
  const response = await fetch(apiUrl(path), {
    signal: AbortSignal.timeout(10000),
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok && !acceptedStatuses.includes(response.status)) {
    // 仅展示稳定码和固定摘要，不回显网络/上游异常或响应中的路径。
    throw new ApiError(payload.code, response.status)
  }
  return payload as T
}

