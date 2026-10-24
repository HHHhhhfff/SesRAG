import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageTimeline from '../src/components/MessageTimeline.vue'
import RunActions from '../src/components/RunActions.vue'
import { renderMarkdown } from '../src/markdown/render'
import type { Message, RunDetail } from '../src/types/api-v2'

// QLT_003：真实产品组件回归；不以工具链Probe替代组件行为。
describe('工作台产品组件质量回归', () => {
  it('清洗Markdown且保留合法结构', () => {
    const html = renderMarkdown('# 标题\n\n**加粗**\n<script>alert(1)</script><img src=x onerror="alert(2)">\n[危险](javascript:alert(3))')
    const root = document.createElement('div'); root.innerHTML = html
    expect(root.querySelector('h1')?.textContent).toBe('标题')
    expect(root.querySelector('strong')?.textContent).toBe('加粗')
    expect(root.querySelector('script,[onerror],a[href^="javascript:"]')).toBeNull()
  })
  it('持久消息可分叉，临时草稿不可分叉，归档均只读', async () => {
    const message: Message = { message_id: 'm1', thread_id: 't', branch_id: 'b', seq: 1, role: 'user', source: 'user_input', content: '原文', status: 'completed', created_at: '2026-10-23T00:00:00Z', run_id: 'r', citations: [] }
    const wrapper = mount(MessageTimeline, { props: { messages: [message, { ...message, message_id: 'projection-r', role: 'assistant' }] } })
    try {
      expect(wrapper.findAll('button')).toHaveLength(1)
      await wrapper.get('button').trigger('click'); expect(wrapper.emitted('fork')).toEqual([['m1']])
      await wrapper.setProps({ readonly: true }); expect(wrapper.findAll('button')).toHaveLength(0)
    } finally { wrapper.unmount() }
  })
  it.each(['queued', 'running', 'cancelling', 'failed', 'cancelled', 'succeeded'] as const)('Run动作遵循%s状态', (status) => {
    // 组件只读取status/legacy，使用满足接口的固定数据，不通过类型断言掩盖缺字段。
    const run: RunDetail = { run_id: 'r', thread_id: 't', branch_id: 'b', user_message_id: 'm', assistant_message_id: null, parent_run_id: null, operation_kind: 'initial', status, cancel_requested_at: null, last_error_code: null, execution_schema_version: 2, legacy: false, model_profile_id: null, model_profile_version: null, model: null, snapshot: null, context_plan: null, created_at: '2026-10-23T00:00:00Z', updated_at: '2026-10-23T00:00:00Z', task: { task_id: 'task', kind: 'run', state: status === 'cancelling' ? 'running' : status, attempt: 1, generation: 1, worker_id: null, last_error_code: null, lease_expires_at: null } }
    const wrapper = mount(RunActions, { props: { run, hasProfile: true } })
    try {
      const text = wrapper.text()
      if (status === 'succeeded') expect(text).toContain('重新生成')
      if (status === 'failed' || status === 'cancelled') expect(text).toContain('重试')
      if (status === 'running' || status === 'queued') expect(text).toContain('停止')
      if (status === 'cancelling') expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    } finally { wrapper.unmount() }
  })
})
