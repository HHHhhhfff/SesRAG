import js from '@eslint/js'
import globals from 'globals'
import vue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

// QLT_003工具前置：前端自行持有Lint配置，不依赖任何PRD验收目录。
export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', '.cache/**', 'coverage/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs['flat/essential'],
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
    },
  },
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
    // Markdown经公共renderMarkdown/DOMPurify清洗后展示；保留提示，不关闭安全清洗。
    rules: { 'vue/no-v-html': 'warn' },
  },
)
