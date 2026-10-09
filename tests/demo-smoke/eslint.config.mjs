import js from '@eslint/js'
import vue from 'eslint-plugin-vue'
import ts from 'typescript-eslint'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'eslint/config'

// QLT_007的后续工具入口：真正的ESLint，不修改frontend的既有lint脚本。
// basePath限定真实前端源码；不能用ignore跳过所有Vue/TS后伪称Lint通过。
const sourceRoot = fileURLToPath(new URL('../../frontend/src/', import.meta.url))
export default defineConfig([
  {
    basePath: sourceRoot,
    files: ['**/*.{ts,vue}'],
    extends: [js.configs.recommended, ...ts.configs.recommended, ...vue.configs['flat/recommended']],
    languageOptions: {
      parserOptions: { parser: ts.parser, extraFileExtensions: ['.vue'] },
      globals: {
        window: 'readonly', document: 'readonly', fetch: 'readonly',
        EventSource: 'readonly', File: 'readonly', FormData: 'readonly',
        URL: 'readonly', Headers: 'readonly', Request: 'readonly', Response: 'readonly',
        console: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
      },
    },
    // .vue内TS类型同样不能被core no-undef判为变量；未定义标识由独立vue-tsc门禁检查。
    // 保留TS/Vue其余推荐规则，不关闭实际Lint以掩盖产品问题。
    rules: { 'no-undef': 'off' },
  },
])
