import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ToolchainProbe from './fixtures/ToolchainProbe.vue'

// 只检查QLT_003需要的Vue/TypeScript/jsdom/计时器基础，不执行工作台产品用例。
describe('前端测试工具链自检', () => {
  afterEach(() => vi.useRealTimers())

  it('编译Vue SFC、传递TypeScript props并接收DOM事件', async () => {
    const wrapper = mount(ToolchainProbe, { props: { label: '工具链就绪' } })
    try {
      expect(wrapper.get('button').text()).toBe('工具链就绪')
      await wrapper.get('button').trigger('click')
      expect(wrapper.emitted('action')).toEqual([['工具链就绪']])
    } finally { wrapper.unmount() }
  })

  it('jsdom提供可观察的DOM变化', async () => {
    const target = document.createElement('div')
    const observed: MutationRecord[] = []
    const observer = new MutationObserver(records => observed.push(...records))
    observer.observe(target, { childList: true })
    try {
      target.textContent = '合成探针'
      await Promise.resolve()
      expect(observed).toHaveLength(1)
      expect(target.textContent).toBe('合成探针')
    } finally { observer.disconnect() }
  })

  it('可控计时器支持后续重连边界测试', () => {
    vi.useFakeTimers()
    const callback = vi.fn()
    setTimeout(callback, 100)
    vi.advanceTimersByTime(99)
    expect(callback).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(callback).toHaveBeenCalledOnce()
  })
})
