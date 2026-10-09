import { defineConfig } from 'vitest/config'
import base from '../vitest.config.mjs'

// 探针独立于产品include；不能让探针的一项通过充当产品组件覆盖。
// mergeConfig会合并include数组，误把产品失败混入工具探针；这里显式替换选择集合。
export default defineConfig({ ...base, test: { ...base.test, include: ['tooling/vitest-tool-probe.test.ts'] } })
