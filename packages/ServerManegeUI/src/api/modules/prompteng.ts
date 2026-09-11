import http from '../http'

/**
 * Prompt 工程 API(ai-service /v1/pe/*,FastAPI 原生 JSON 响应,无统一包装)。
 * ai-service 以 X-User-Id 头标识管理台用户(鉴权约定见 app/deps.py),
 * 这里从本地会话取用户 ID 透传。
 */

export interface PeTemplate {
  id: string
  key: string
  name: string
  group: string
  description: string
  status: string
  current_version: number
  created_at?: string
  updated_at?: string
}

export interface PeVersion {
  id: string
  template_id: string
  version: number
  content: string
  variables: Array<{ name: string; desc?: string; required?: boolean }>
  status: string
  note: string
  created_at?: string
}

export interface PeTemplateStat {
  template_key: string
  call_count: number
  avg_prompt_tokens: number | null
  avg_latency_ms: number
  versions: Array<{ version: number; call_count: number }>
  eval_pass_rate: number | null
}

export interface PeOverview {
  days: number
  total_calls: number
  active_templates: number
  silent_templates: string[]
  templates: PeTemplateStat[]
}

export interface PeTrendPoint {
  date: string
  version: number
  call_count: number
  avg_prompt_tokens: number | null
  avg_latency_ms: number
}

/** 当前登录用户 ID(供 ai-service X-User-Id 头;与 auth store 同源) */
function uid(): string {
  try {
    return JSON.parse(localStorage.getItem('gw_user') || 'null')?.id ?? ''
  } catch {
    return ''
  }
}

const headers = () => ({ 'X-User-Id': uid() })

export interface PeVariable {
  name: string
  desc?: string
  required?: boolean
}

export interface PeVersionPayload {
  content?: string
  variables?: PeVariable[]
  note?: string
}

export const promptApi = {
  listTemplates: (group?: string) =>
    http.get<{ templates: PeTemplate[] }>('/v1/pe/templates', { params: { group }, headers: headers() }),
  createTemplate: (body: Partial<PeTemplate> & { content?: string; variables?: unknown[] }) =>
    http.post<PeTemplate>('/v1/pe/templates', body, { headers: headers() }),
  deleteTemplate: (key: string) =>
    http.delete<{ ok: boolean }>(`/v1/pe/templates/${key}`, { headers: headers() }),
  listVersions: (key: string) =>
    http.get<{ versions: PeVersion[] }>(`/v1/pe/templates/${key}/versions`, { headers: headers() }),
  addVersion: (key: string, body: { content: string; variables?: PeVariable[]; note?: string }) =>
    http.post<PeVersion>(`/v1/pe/templates/${key}/versions`, body, { headers: headers() }),
  updateVersion: (key: string, version: number, body: PeVersionPayload) =>
    http.put<PeVersion>(`/v1/pe/templates/${key}/versions/${version}`, body, { headers: headers() }),
  deleteVersion: (key: string, version: number) =>
    http.delete<{ ok: boolean }>(`/v1/pe/templates/${key}/versions/${version}`, { headers: headers() }),
  activate: (key: string, version: number, note?: string) =>
    http.post<PeTemplate>(`/v1/pe/templates/${key}/activate`, { version, note }, { headers: headers() }),
  disable: (key: string) =>
    http.post<PeTemplate>(`/v1/pe/templates/${key}/disable`, {}, { headers: headers() }),
  overview: (days = 30) =>
    http.get<PeOverview>('/v1/pe/metrics/overview', { params: { days }, headers: headers() }),
  templateTrend: (key: string, days = 14) =>
    http.get<{ template_key: string; days: number; points: PeTrendPoint[] }>(
      `/v1/pe/metrics/templates/${key}`, { params: { days }, headers: headers() }),
}
