import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

/**
 * 统一响应格式(见同目录 api.json):
 *   普通接口: { "errCode": "0", "errMsg": "请求成功", "data": {...} }
 *   分页接口: { "errCode": "0", "errMsg": "...", "data": [...], "total": 1 }
 * errCode = "0" 表示成功,其余为业务错误码
 */
export interface ApiResponse<T> {
  errCode: string
  errMsg: string
  data: T
  /** 仅分页接口返回总记录数 */
  total?: number
}

/** 分页接口响应: data 为当前页列表, total 为总记录数 */
export interface ApiPageResponse<T> extends ApiResponse<T[]> {
  total: number
}

const SUCCESS_CODE = '0'

/** 校验响应体是否符合 api.json 约定的统一格式 */
function isApiResponse(body: unknown): body is ApiResponse<unknown> {
  if (!body || typeof body !== 'object') return false
  const b = body as Record<string, unknown>
  return typeof b.errCode === 'string' && typeof b.errMsg === 'string'
}

const http = axios.create({ baseURL: '/', timeout: 90_000 })

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (resp) => {
    // OpenAI 兼容接口(/v1)与 NestJS 原生接口(/nestjs)透传原始响应,不做包装校验
    if (resp.config.url?.startsWith('/v1') || resp.config.url?.startsWith('/nestjs')) {
      return resp
    }
    const body = resp.data as unknown
    if (!isApiResponse(body)) {
      ElMessage.error('接口响应格式不符合统一规范')
      return Promise.reject(new Error('invalid api response format'))
    }
    if (body.errCode !== SUCCESS_CODE) {
      ElMessage.error(body.errMsg || '请求失败')
      return Promise.reject(new Error(body.errMsg))
    }
    return resp
  },
  (err) => {
    const status = err.response?.status
    const body = err.response?.data
    // NestJS 错误体为 { message } 或 OpenAI 风格 { error: { message } }
    const nestMsg =
      (body as { error?: { message?: string }; message?: string } | undefined)?.error?.message ??
      (body as { message?: string } | undefined)?.message
    const msg = (isApiResponse(body) && body.errMsg) || nestMsg || err.message || '网络错误'
    if (status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push({ name: 'login' })
    }
    ElMessage.error(msg)
    return Promise.reject(err)
  },
)

export default http
