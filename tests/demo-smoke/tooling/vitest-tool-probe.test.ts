import { expect, test } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia, defineStore, setActivePinia } from 'pinia'

// 仅证明Vitest/jsdom/Vue挂载与DOM事件工具可用，不对应任何产品用例。
test('工具探针：Vue组件可挂载、点击并卸载', async () => {
  const component = defineComponent({
    setup() {
      const count = ref(0)
      return () => h('button', { onClick: () => count.value++ }, String(count.value))
    },
  })
  const wrapper = mount(component)
  try {
    expect(wrapper.text()).toBe('0')
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toBe('1')
  } finally {
    wrapper.unmount()
  }
})

// FE store用例工具前提：测试目录直接import Pinia且与组件共享响应式runtime。
test('工具探针：Pinia可直接导入并驱动组件更新', async () => {
  setActivePinia(createPinia())
  const useProbeStore = defineStore('tool-only-store', {
    state: () => ({ count: 0 }),
    actions: { increment() { this.count++ } },
  })
  const component = defineComponent({
    setup() {
      const store = useProbeStore()
      return () => h('button', { onClick: () => store.increment() }, String(store.count))
    },
  })
  const wrapper = mount(component)
  try {
    expect(wrapper.text()).toBe('0')
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toBe('1')
  } finally {
    wrapper.unmount()
    setActivePinia(undefined)
  }
})
