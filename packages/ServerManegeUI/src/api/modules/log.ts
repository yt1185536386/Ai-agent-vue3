import http from '../http'
import type { ApiPageResponse } from '../http'
import type { InvokeLog } from '../types'

/**
 * 调用日志(Java model-gateway /api/logs,唯一计量来源)。
 * 响应为网关统一包装的分页结构 { errCode, errMsg, data, total }。
 * 时间参数按 ISO LocalDateTime(带 T)传给后端。
 */
export const logApi = {
  page: (params: Record<string, unknown>) =>
    http.get<ApiPageResponse<InvokeLog>>('/api/logs', {
      params: {
        ...params,
        start: (params.startTime as string | undefined)?.replace(' ', 'T'),
        end: (params.endTime as string | undefined)?.replace(' ', 'T'),
        startTime: undefined,
        endTime: undefined,
      },
    }),
}
