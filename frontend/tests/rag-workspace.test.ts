import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import DocumentUploader from '../src/components/DocumentUploader.vue'
import { useRagStore } from '../src/stores/rag'
import { useDocumentStore } from '../src/stores/documents'
import { renderMarkdown } from '../src/markdown/render'
import * as api from '../src/api/v3/rag'

vi.mock('../src/api/v3/rag', () => ({
  uploadDocument: vi.fn(), listDocuments: vi.fn(), createDiagnostic: vi.fn(),
  getExecution: vi.fn(), rebuildDocument: vi.fn(),
}))

beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  useRagStore().selectedBase = 'base'
  vi.mocked(api.listDocuments).mockResolvedValue({ items: [], next_cursor: null })
})

async function selectFile(wrapper: ReturnType<typeof mount>, name: string) {
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { configurable: true,
    value: [new File(['synthetic'], name)] })
  await input.trigger('change')
}

describe('PRD-003固定路由和外发边界', () => {
  it('超范围的检索参数在提交前明确提示', async () => {
    const rag = useRagStore()
    rag.enabled = true; rag.topK = 21
    expect(() => rag.selection()).toThrow('INVALID_RAG_PARAMETER')
    await rag.diagnose('question')
    expect(api.createDiagnostic).not.toHaveBeenCalled()
    expect(rag.error).toContain('Top-K')
  })
  it('文本提交不带云端授权字段', async () => {
    const wrapper = mount(DocumentUploader)
    await selectFile(wrapper, 'local.md')
    await wrapper.get('form').trigger('submit')
    expect(api.uploadDocument).toHaveBeenCalledWith('base', expect.any(File), {}, [], expect.any(String))
    wrapper.unmount()
  })

  it('未验证的办公能力不能提交且显示不可用', async () => {
    const wrapper = mount(DocumentUploader)
    await selectFile(wrapper, 'office.pdf')
    expect(wrapper.text()).toContain('当前无法提交')
    await wrapper.get('form').trigger('submit')
    expect(api.uploadDocument).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('每次选取办公原件均需重新勾选外发授权', async () => {
    useRagStore().profiles = [{ kind: 'parser', profile_id: 'mineru-office', version: 2,
      available: true, unavailable_reason: null, formats: ['.pdf'], verified_formats: ['.pdf'],
      space_id: null, dimension: null }]
    const wrapper = mount(DocumentUploader)
    await selectFile(wrapper, 'first.pdf')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await selectFile(wrapper, 'second.pdf')
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false)
    await wrapper.get('form').trigger('submit')
    expect(api.uploadDocument).not.toHaveBeenCalled()
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('form').trigger('submit')
    expect(api.uploadDocument).toHaveBeenCalledWith('base', expect.any(File),
      { cloud_consent: true, consent_version: 'mineru-office-outbound-v1', acknowledge_duplicate_cost: false }, [], expect.any(String))
    wrapper.unmount()
  })

  it('关闭RAG无隐式检索配置，诊断迟到结果不能覆盖切换后视图', async () => {
    const rag = useRagStore()
    expect(rag.selection()).toEqual({ enabled: false })
    let resolve!: (value: never) => void
    vi.mocked(api.createDiagnostic).mockReturnValue(new Promise(done => { resolve = done }))
    const pending = rag.diagnose('question')
    rag.resetDiagnostic()
    resolve({ execution_id: 'old' } as never)
    await pending
    expect(rag.diagnostic).toBeNull()
    expect(api.getExecution).not.toHaveBeenCalled()
  })

  it('不可信Markdown不生成远端图片、iframe、样式和脚本', () => {
    const html = renderMarkdown('![exfil](https://remote.invalid/a) <iframe src="https://remote.invalid" /> <script>alert(1)</script><p style="background:url(https://remote.invalid)">text</p>')
    const node = document.createElement('div')
    node.innerHTML = html
    expect(node.querySelector('img,iframe,script,style,svg,object')).toBeNull()
    expect(node.querySelector('[style]')).toBeNull()
  })

  it('已知的客户端拒绝允许改正输入，不把请求永远锁为未知上传', async () => {
    const { ApiError } = await import('../src/api/http')
    vi.mocked(api.uploadDocument).mockRejectedValueOnce(new ApiError('INVALID_RAG_PARAMETER', 422))
    const store = useDocumentStore()
    await store.upload(new File(['a'], 'a.txt'))
    await flushPromises()
    expect(store.pendingUpload).toBe(false)
  })
})
