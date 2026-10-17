import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const proxyTarget = env.API_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': proxyTarget,
      '/health': proxyTarget,
    },
  },
  }
})

