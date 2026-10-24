// COMP_001～COMP_013：v1/v2契约和迁移用例执行矩阵关联的真实回归模块。
import { runBackendRegressionCategory } from '../tooling/product-category.mjs';
import { compatibilityRuntime } from './compatibility-runtime.mjs';
runBackendRegressionCategory('compatibility', process.argv[process.argv.indexOf('--context') + 1], compatibilityRuntime)
  .then((code) => { process.exitCode = code; })
  .catch((error) => { console.error(`【compatibility】执行错误：${error.message}`); process.exitCode = 2; });
