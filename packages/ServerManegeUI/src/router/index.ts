import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * 路由 meta.perm: 菜单与路由守卫共用同一套权限判断。
 *   'super'   → 仅超级管理员
 *   '_manager'→ 部门经理(操作者 deptPosition === 'MANAGER')
 *   权限码数组 → 持有任一权限码即可(超管恒通过,见 auth.hasPerm)
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login/index.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/layout/AdminLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard/index.vue'), meta: { title: '数据看板', perm: 'super' } },
        { path: 'invoke', name: 'invoke', component: () => import('@/views/ModelInvoke/index.vue'), meta: { title: '模型调试台' } },
        { path: 'profile', name: 'profile', component: () => import('@/views/PersonalCenter/index.vue'), meta: { title: '个人中心' } },
        { path: 'channels', name: 'channels', component: () => import('@/views/Channels/index.vue'), meta: { title: '渠道管理', perm: 'super' } },
        { path: 'users', name: 'users', component: () => import('@/views/Users/index.vue'), meta: { title: '用户管理', perm: ['dept:member', '_manager'] } },
        { path: 'departments', name: 'departments', component: () => import('@/views/Departments/index.vue'), meta: { title: '部门管理', perm: ['dept:info', 'dept:member', '_manager'] } },
        { path: 'permissions', name: 'permissions', component: () => import('@/views/Permissions/index.vue'), meta: { title: '权限维护', perm: ['dept:member', '_manager'] } },
        { path: 'logs', name: 'logs', component: () => import('@/views/Logs/index.vue'), meta: { title: '调用日志', perm: ['log:view'] } },
        { path: 'alerts', name: 'alerts', component: () => import('@/views/Alerts/index.vue'), meta: { title: '告警中心', perm: 'super' } },
        { path: 'policies', name: 'policies', component: () => import('@/views/Policies/index.vue'), meta: { title: '限流熔断', perm: ['policy:manage'] } },
        { path: 'prompt/templates', name: 'prompt-templates', component: () => import('@/views/PromptTemplates/index.vue'), meta: { title: 'Prompt 模板', perm: ['prompt:manage'] } },
        { path: 'prompt/metrics', name: 'prompt-metrics', component: () => import('@/views/PromptMetrics/index.vue'), meta: { title: 'Prompt 监控', perm: ['prompt:view'] } },
        { path: 'context/events', name: 'context-events', component: () => import('@/views/ContextEvents/index.vue'), meta: { title: '检索与快照', perm: ['ctx:view'] } },
        { path: 'context/metrics', name: 'context-metrics', component: () => import('@/views/ContextMetrics/index.vue'), meta: { title: 'Context 监控', perm: ['ctx:view'] } },
      ],
    },
  ],
})

/** 路由级权限判断(与 AdminLayout 菜单显隐同一逻辑) */
export function allowByPerm(auth: ReturnType<typeof useAuthStore>, perm?: string | string[]) {
  if (!perm) return true
  if (auth.isSuper) return true
  if (perm === 'super') return false
  const codes = Array.isArray(perm) ? perm : [perm]
  return codes.some((code) => {
    if (code === '_manager') return auth.isManager
    return auth.hasPerm(code)
  })
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return
  if (!auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 刷新后首次进入:拉取有效权限码(菜单显隐与守卫都依赖它)
  if (auth.codes == null) {
    try {
      await auth.loadPerms()
    } catch {
      // 失败(如 401)由 http 拦截器统一处理跳转登录
      return
    }
  }
  if (!allowByPerm(auth, to.meta.perm as string | string[] | undefined)) {
    return { name: 'profile' }
  }
})

export default router
