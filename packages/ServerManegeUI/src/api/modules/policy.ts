import http from '../http'
import type { ApiResponse } from '../http'
import type { Policy } from '../types'

/** 限流/熔断策略 */
export const policyApi = {
  list: (type?: string) => http.get<ApiResponse<Policy[]>>('/api/policies', { params: { type } }),
  create: (data: Partial<Policy>) => http.post('/api/policies', data),
  update: (id: string, data: Partial<Policy>) => http.put(`/api/policies/${id}`, data),
  remove: (id: string) => http.delete(`/api/policies/${id}`),
}
