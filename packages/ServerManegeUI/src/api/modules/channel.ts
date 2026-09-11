import http from '../http'
import type { ApiResponse } from '../http'
import type { Channel, ChannelPayload } from '../types'

/** 仓库(渠道)管理 */
export const channelApi = {
  list: () => http.get<ApiResponse<Channel[]>>('/api/channels'),
  create: (data: ChannelPayload) => http.post('/api/channels', data),
  update: (id: string, data: ChannelPayload) => http.put(`/api/channels/${id}`, data),
  changeStatus: (id: string, status: number) => http.put(`/api/channels/${id}/status`, { status }),
  remove: (id: string) => http.delete(`/api/channels/${id}`),
  /** 真实调用上游 GET {baseUrl}/models 拉取模型列表(按认证字段附 Key) */
  fetchModels: (data: { baseUrl: string; apiKey: string; authType?: string }) =>
    http.post<ApiResponse<string[]>>('/api/channels/fetch-models', data),
}
