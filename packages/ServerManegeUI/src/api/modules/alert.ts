import http from '../http'
import type { ApiResponse, ApiPageResponse } from '../http'
import type { AlertRule, AlertRecord } from '../types'

/** 告警中心(Java model-gateway /api/alerts,仅超管) */
export const alertApi = {
  // 规则管理
  rules: () => http.get<ApiResponse<AlertRule[]>>('/api/alerts/rules'),
  createRule: (data: Partial<AlertRule>) => http.post('/api/alerts/rules', data),
  updateRule: (id: string, data: Partial<AlertRule>) => http.put(`/api/alerts/rules/${id}`, data),
  removeRule: (id: string) => http.delete(`/api/alerts/rules/${id}`),
  // 触发记录
  records: (params: Record<string, unknown>) =>
    http.get<ApiPageResponse<AlertRecord>>('/api/alerts/records', { params }),
  unreadCount: () => http.get<ApiResponse<number>>('/api/alerts/records/unread-count'),
  markRead: (id: string) => http.put(`/api/alerts/records/${id}/read`),
  markAllRead: () => http.put('/api/alerts/records/read-all'),
}
