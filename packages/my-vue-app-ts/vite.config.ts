import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const nestPort = process.env.NESTJS_PORT || '26011'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        // 手动分包:渲染相关库变动少,独立成 chunk 可利用浏览器长缓存
        // (Vite 8/Rolldown 仅支持函数形式)
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return
          if (id.includes('highlight.js')) return 'vendor-hljs'
          if (id.includes('markdown-it') || id.includes('js-beautify'))
            return 'vendor-markdown'
        },
      },
    },
  },
  server: {
    port: parseInt(process.env.VITE_PORT || '26012', 10),
    proxy: {
      '/api': {
        target: `http://localhost:${nestPort}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
