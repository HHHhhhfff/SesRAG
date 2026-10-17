import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

const here = fileURLToPath(new URL('.', import.meta.url))
// QLT_007/FE store与组件用例后续接入：测试工具Vue版本与前端一致。
// Node包装入口复用test-utils的CJS runtime；不能混用esm-bundler与CJS reactivity。
const testVue = fileURLToPath(new URL('node_modules/vue/index.mjs', import.meta.url))
// 直接import Pinia的测试也走产品同一模块，不能在测试包另装一份activePinia。
const frontendPinia = fileURLToPath(new URL('../../frontend/node_modules/pinia/dist/pinia.mjs', import.meta.url))
export default defineConfig({
  root: here,
  cacheDir: '.cache/vite',
  plugins: [vue()],
  resolve: {
    alias: [
      { find: /^vue$/, replacement: testVue },
      { find: /^pinia$/, replacement: frontendPinia },
    ],
    dedupe: ['vue', 'pinia'],
  },
  test: {
    environment: 'jsdom',
    // test-utils若外置require自己的Vue，会绕过alias形成两份reactivity。
    // 以内联转换应用同一alias，确保后续FE组件用例的点击/nextTick真实生效。
    server: { deps: { inline: ['@vue/test-utils', 'pinia', 'vue-demi'] } },
    include: ['specific_test_script/**/*.{test,spec}.{ts,js,mjs}'],
    passWithNoTests: false,
    testTimeout: 10000,
    hookTimeout: 10000,
    reporters: ['default'],
  },
})
