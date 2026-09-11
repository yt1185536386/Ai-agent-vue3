import http from '../http'

/**
 * Context 工程 API(ai-service /v1/cx/*,FastAPI 原生 JSON 响应)。
 * X-User-Id 头约定同 prompteng.ts。
 */

export interface RetrievalEvent {
  id: string
  user_id: string
  conversation_id: string
  query: string
  strategy: string
  top_k: number
  threshold: number
  hit_count: number
  max_score: number
  latency_ms: number
  created_at?: string
  hits?: Array<{ chunk_id: string; doc_id: string; score: number; position: number }>
}

export interface ContextSnapshot {
  id: string
  conversation_id: string
  user_id: string
  model: string
  total_tokens: number
  system_tokens: number
  history_tokens: number
  tool_tokens: number
  message_count: number
  rag_chunk_ids: string[]
  rag_injected: number
  truncated: number
  created_at?: string
}

export interface CxOverview {
  days: number
  retrieval_count: number
  zero_result_rate: number
  avg_max_score: number
  avg_hit_count: number
  avg_retrieval_latency_ms: number
  score_histogram: Array<{ lo: number; hi: number; count: number }>
  snapshot_count: number
  rag_inject_rate: number
  avg_context_tokens: number
  p95_context_tokens: number
  zero_result_top: Array<{ query: string; count: number; avg_max_score: number }>
  low_score_events: Array<{ id: string; query: string; max_score: number; hit_count: number; created_at?: string }>
}

export interface CxTrendPoint {
  date: string
  retrieval_count?: number
  zero_result_rate?: number
  avg_max_score?: number
  snapshot_count?: number
  rag_inject_rate?: number
  avg_context_tokens?: number
  p95_context_tokens?: number
  avg_system_tokens?: number
  avg_history_tokens?: number
  avg_tool_tokens?: number
  recall_at_k?: number | null
  precision_at_k?: number | null
}

export interface EvalCase {
  id: string
  query: string
  expect_doc_ids: string[]
  expect_contains: string[]
  source: string
  status: string
  created_at?: string
}

export interface Strategy {
  strategy: string
  size: number
  overlap: number
  top_k: number
  threshold: number
}

function uid(): string {
  try {
    return JSON.parse(localStorage.getItem('gw_user') || 'null')?.id ?? ''
  } catch {
    return ''
  }
}

const headers = () => ({ 'X-User-Id': uid() })

export const contextApi = {
  retrievalEvents: (params: Record<string, unknown>) =>
    http.get<{ total: number; page: number; size: number; events: RetrievalEvent[] }>(
      '/v1/cx/retrieval/events', { params, headers: headers() }),
  retrievalEvent: (id: string) =>
    http.get<RetrievalEvent>(`/v1/cx/retrieval/events/${id}`, { headers: headers() }),
  snapshots: (params: Record<string, unknown>) =>
    http.get<{ total: number; page: number; size: number; snapshots: ContextSnapshot[] }>(
      '/v1/cx/snapshots', { params, headers: headers() }),
  overview: (days = 30) =>
    http.get<CxOverview>('/v1/cx/metrics/overview', { params: { days }, headers: headers() }),
  trends: (days = 14) =>
    http.get<{ days: number; series: CxTrendPoint[] }>('/v1/cx/metrics/trends',
      { params: { days }, headers: headers() }),
  evalCases: (params?: Record<string, unknown>) =>
    http.get<{ cases: EvalCase[] }>('/v1/cx/eval-cases', { params, headers: headers() }),
  createEvalCase: (body: { query: string; expect_doc_ids?: string[]; expect_contains?: string[] }) =>
    http.post<EvalCase>('/v1/cx/eval-cases', body, { headers: headers() }),
  recycleEvalCase: (body: { event_id: string; expect_doc_ids?: string[]; expect_contains?: string[] }) =>
    http.post<{ id: string; query: string; source: string }>('/v1/cx/eval-cases/recycle', body,
      { headers: headers() }),
  runEval: (body?: { top_k?: number; threshold?: number; user_id?: string }) =>
    http.post<Record<string, unknown>>('/v1/cx/eval/run', body ?? {}, { headers: headers() }),
  getStrategy: () =>
    http.get<Strategy>('/v1/cx/strategy', { headers: headers() }),
  updateStrategy: (body: Partial<Strategy>) =>
    http.post<Strategy>('/v1/cx/strategy', body, { headers: headers() }),
}
