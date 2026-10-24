import DOMPurify from 'dompurify'
import { marked } from 'marked'

// 保存正文和流式草稿都走同一入口，禁止危险协议、事件属性和脚本节点。
const purifier = (value: string) => DOMPurify.sanitize(value, {
  USE_PROFILES: { html: true },
  FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form'],
  FORBID_ATTR: ['style', 'onerror', 'onclick', 'onload', 'onmouseover'],
  ALLOW_UNKNOWN_PROTOCOLS: false,
})
export function renderMarkdown(source: string) { return purifier(marked.parse(source, { async: false }) as string) }
