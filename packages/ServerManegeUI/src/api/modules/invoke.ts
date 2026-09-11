import http from '../http'
import type { ApiResponse } from '../http'

/** 模型调用 */
export const invokeApi = {
  chat: (payload: { model: string; messages: { role: string; content: string }[]; stream?: boolean }) =>
    http.post<ApiResponse<Record<string, unknown>>>('/api/invoke/chat', payload),
}
