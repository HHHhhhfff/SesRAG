import { runCategory } from '../lib/category-kit.mjs'
import { runPersistentFrontend } from './frontend-persistent.mjs'
import { runFrontendComponents } from './frontend-components.mjs'

// 5c专项只消费明确新增检查，不伪装正常FE分类或正式all。
await runCategory('fe', async s => {
  if (process.env.SMOKE_FRONTEND_MODE === 'components') await runFrontendComponents(s)
  else await runPersistentFrontend(s, process.env.SMOKE_FRONTEND_SUB)
})
