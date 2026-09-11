import http from '../http'
import type { ApiResponse } from '../http'
import type { SafeUser } from '@/stores/auth'

/** NestJS 登录响应(原生结构,非 Java 网关统一包装) */
export interface NestLoginResponse {
  access_token: string
  user: SafeUser
}

/**
 * 鉴权:登录统一走 NestJS 业务网关(/nestjs 代理),
 * Java 网关只校验 NestJS 签发的 JWT(共享密钥),不再签发。
 */
export const authApi = {
  login: (username: string, password: string) =>
    http.post<NestLoginResponse>('/nestjs/auth/login', { username, password }),
  me: () => http.get<ApiResponse<SafeUser>>('/api/auth/me'),
}
