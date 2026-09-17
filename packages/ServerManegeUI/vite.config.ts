import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入:模板组件与 ElMessage 等 API 自动注入对应样式
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 26013,
    proxy: {
      // ai-service(Prompt 工程 / Context 工程,26010)——
      // 必须放在 '/v1' 之前,vite 按声明顺序匹配前缀
      '/v1/pe': 'http://localhost:26010',
      '/v1/cx': 'http://localhost:26010',
      // Java 网关 model-gateway(模型出口,26015)
      '/api': 'http://localhost:26015',
      '/v1': 'http://localhost:26015',
      // NestJS 后端(模型管理 / 调用日志在 NestJS 侧)
      '/nestjs': {
        target: 'http://localhost:26011',
        rewrite: (p) => p.replace(/^\/nestjs/, ''),
      },
    },
  },
})
