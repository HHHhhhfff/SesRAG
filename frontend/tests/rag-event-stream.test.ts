import { beforeEach, describe, expect, it, vi } from 'vitest'
import { openV3RunStream, parseV3Event, replayV3Events } from '../src/events/rag-event-stream'
import * as api from '../src/api/v3/sessions'

vi.mock('../src/api/v3/sessions', () => ({ getEvents: vi.fn() }))
const valid = {
  schema_version: 3, event_id: 'event', run_id: 'run', seq: 1, type: 'tool.stage',
  occurred_at: '2026-11-12T00:00:00Z',
  data: { task_id: 'task', attempt: 1, generation: 1, call_id: 'call', execution_id: 'execution', tool_version: 1, stage: 'dense' },
}
beforeEach(() => { vi.resetAllMocks() })

describe('RAG-DEF-010 正式RunEvent Schema运行时校验', () => {
  it('合法工具事件不修改载荷，接受count的契约边界', () => {
    expect(parseV3Event(valid)).toBe(valid)
    for (const count of [null, 0, 100]) expect(parseV3Event({ ...valid, data: { ...valid.data, count } }).data).toEqual({ ...valid.data, count })
  })

  it.each([
    ['未知协议', { ...valid, schema_version: 99 }],
    ['seq=0', { ...valid, seq: 0 }],
    ['未知kind', { ...valid, type: 'unknown' }],
    ['generation=0', { ...valid, data: { ...valid.data, generation: 0 } }],
    ['tool_version=99', { ...valid, data: { ...valid.data, tool_version: 99 } }],
    ['负count', { ...valid, data: { ...valid.data, count: -1 } }],
    ['count超过上限', { ...valid, data: { ...valid.data, count: 101 } }],
    ['count不接受字符串', { ...valid, data: { ...valid.data, count: '1' } }],
    ['未知mode', { ...valid, data: { ...valid.data, mode: 'success' } }],
    ['附加信封字段', { ...valid, extra: 'secret' }],
    ['附加载荷字段', { ...valid, data: { ...valid.data, extra: 'secret' } }],
    ['非法日期', { ...valid, occurred_at: 'not-a-date' }],
    ['非法日历日期', { ...valid, occurred_at: '2026-02-30T00:00:00Z' }],
    ['缺少event_id', Object.fromEntries(Object.entries(valid).filter(([key]) => key !== 'event_id'))],
  ])('%s必须拒绝', (_label, value) => {
    expect(() => parseV3Event(value)).toThrow()
  })

  it.each([1, 2, 3])('正式联合契约中的schema%s历史delta仍可读取', schema_version => {
    const delta = { ...valid, schema_version, type: 'answer.delta', data: schema_version === 1 ? { text: '历史' } : { task_id: 'task', attempt: 1, generation: 1, text: '历史' } }
    expect(parseV3Event(delta)).toBe(delta)
    expect(() => parseV3Event({ ...delta, data: { ...delta.data, extra: 'untrusted' } })).toThrow()
  })

  it('HTTP补放遇到非法事件时拒绝投影', async () => {
    vi.mocked(api.getEvents).mockResolvedValue({ events: [{ ...valid, data: { ...valid.data, count: -1 } }] as never, has_more: false, next_after_seq: 1 })
    const onEvent = vi.fn()
    await expect(replayV3Events('run', 0, onEvent)).rejects.toThrow('EVENT_SCHEMA_INVALID')
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('SSE非法事件关闭连接并提供稳定错误，不追加或宣布Run终态', async () => {
    const listeners = new Map<string, EventListener>()
    const close = vi.fn()
    class Source {
      close = close
      addEventListener(kind: string, listener: EventListener) { listeners.set(kind, listener) }
      onerror = null
    }
    vi.stubGlobal('EventSource', Source)
    vi.mocked(api.getEvents).mockResolvedValue({ events: [], has_more: false, next_after_seq: 0 })
    const onEvent = vi.fn(); const onError = vi.fn(); const onReady = vi.fn()
    try {
      openV3RunStream('run', 0, onEvent, onError, onReady)
      listeners.get('tool.stage')!(new MessageEvent('tool.stage', { data: JSON.stringify({ ...valid, data: { ...valid.data, tool_version: 99 } }) }))
      await Promise.resolve()
      expect(close).toHaveBeenCalledOnce()
      expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: 'EVENT_SCHEMA_INVALID' }))
      expect(onEvent).not.toHaveBeenCalled()
      expect(onReady).not.toHaveBeenCalled()
    } finally { vi.unstubAllGlobals() }
  })
})
