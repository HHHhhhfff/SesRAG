// RUN_001～RUN_030：Run事务、事件、取消、租约与故障行为执行隔离后端回归断言。
import { runBackendRegressionCategory } from '../tooling/product-category.mjs';
import { runtimeCases } from './run-runtime.mjs';
runBackendRegressionCategory('run', process.argv[process.argv.indexOf('--context') + 1], runtimeCases)
  .then((code) => { process.exitCode = code; })
  .catch((error) => { console.error(`【run】执行错误：${error.message}`); process.exitCode = 2; });
