// SES_001～SES_018：按正式测试点关联到隔离 pytest 回归模块并逐例汇总证据。
import { runBackendRegressionCategory } from '../tooling/product-category.mjs';
import { sessionRuntime } from './session-runtime.mjs';
runBackendRegressionCategory('session', process.argv[process.argv.indexOf('--context') + 1], sessionRuntime)
  .then((code) => { process.exitCode = code; })
  .catch((error) => { console.error(`【session】执行错误：${error.message}`); process.exitCode = 2; });
