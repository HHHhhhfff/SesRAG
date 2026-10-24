// CTX_001～CTX_013：历史、预算、摘要和证据用例使用测试点矩阵关联的真实后端断言。
import { runBackendRegressionCategory } from '../tooling/product-category.mjs';
import { contextRuntime } from './context-runtime.mjs';
runBackendRegressionCategory('context', process.argv[process.argv.indexOf('--context') + 1], contextRuntime)
  .then((code) => { process.exitCode = code; })
  .catch((error) => { console.error(`【context】执行错误：${error.message}`); process.exitCode = 2; });
