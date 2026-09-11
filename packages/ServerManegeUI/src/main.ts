import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus 组件与样式由 unplugin-vue-components 按需注入(vite.config.ts);
// 中文语言包在 App.vue 的 <el-config-provider> 中配置。
// ElMessage / ElMessageBox 在视图里是显式 JS 导入,不走模板解析,
// 其样式需要在这里手动引入,否则弹出的消息没有样式。
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import * as Icons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
for (const [name, comp] of Object.entries(Icons)) {
  app.component(name, comp)
}
app.mount('#app')
