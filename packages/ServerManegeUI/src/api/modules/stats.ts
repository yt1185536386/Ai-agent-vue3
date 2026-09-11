import http from '../http'
import type { ApiResponse } from '../http'
import type { Overview } from '../types'

/** 数据概览 */
export const statsApi = {
  overview: (params: { start: string; end: string; username?: string }) =>
    http.get<ApiResponse<Overview>>('/api/stats/overview', { params }),
  realtime: () =>
    http.get<ApiResponse<{ callsLastMinute: number; tokensLastMinute: number; errorsLastMinute: number }>>('/api/stats/realtime'),
}
