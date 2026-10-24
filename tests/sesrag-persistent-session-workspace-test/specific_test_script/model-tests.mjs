// MOD_001～MOD_008：Profile、快照及凭据行为执行隔离后端回归断言。
import { runBackendRegressionCategory } from '../tooling/product-category.mjs';
import { modelRuntime } from './model-runtime.mjs';
runBackendRegressionCategory('model', process.argv[process.argv.indexOf('--context') + 1], modelRuntime)
  .then((code) => { process.exitCode = code; })
  .catch((error) => { console.error(`【model】执行错误：${error.message}`); process.exitCode = 2; });
