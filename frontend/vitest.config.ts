import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// QLT_003工具前置：独立配置不加载开发Vite代理或仓库根.env。
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
    passWithNoTests: false,
    testTimeout: 10000,
    clearMocks: true,
    restoreMocks: true,
  },
})
