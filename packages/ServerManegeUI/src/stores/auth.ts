import { defineStore } from 'pinia'
import { myPermApi } from '@/api/modules/org'

export interface SafeUser {
  id: string
  username: string
  email?: string
  displayName?: string
  avatar?: string
  isSuperAdmin: boolean
  jobLevel?: { id: number; name: string; rank: number } | null
  department?: { id: number; name: string } | null
  deptPosition?: 'MANAGER' | 'DEPUTY' | 'LEADER' | 'MEMBER'
  status: number
  lastLoginAt?: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('gw_token') || '',
    user: JSON.parse(localStorage.getItem('gw_user') || 'null') as SafeUser | null,
    /** 有效权限码(个人绑定逐项覆盖职级绑定);null = 尚未拉取 */
    codes: JSON.parse(localStorage.getItem('gw_codes') || 'null') as string[] | null,
  }),
  getters: {
    isSuper: (s) => !!s.user?.isSuperAdmin,
    isManager: (s) => s.user?.deptPosition === 'MANAGER',
    hasPerm: (s) => (code: string) =>
      !!s.user?.isSuperAdmin || (s.codes?.includes(code) ?? false),
  },
  actions: {
    setSession(token: string, user: SafeUser) {
      this.token = token
      this.user = user
      this.codes = null
      localStorage.setItem('gw_token', token)
      localStorage.setItem('gw_user', JSON.stringify(user))
      localStorage.removeItem('gw_codes')
    },
    setCodes(codes: string[]) {
      this.codes = codes
      localStorage.setItem('gw_codes', JSON.stringify(codes))
    },
    /** 拉取当前用户有效权限(登录后 / 刷新后首次进入受控路由时调用) */
    async loadPerms() {
      const { data } = await myPermApi.mine()
      this.setCodes(data.permissions)
    },
    logout() {
      this.token = ''
      this.user = null
      this.codes = null
      localStorage.removeItem('gw_token')
      localStorage.removeItem('gw_user')
      localStorage.removeItem('gw_codes')
    },
  },
})
