import type { AxiosRequestConfig } from "axios";

/**
 * 扩展 axios 请求配置，支持在拦截器中跳过自动鉴权。
 */
export interface RequestConfig extends AxiosRequestConfig {
  skipAuth?: boolean;
}

declare module "axios" {
  interface InternalAxiosRequestConfig {
    skipAuth?: boolean;
  }
}

/**
 * 后端统一错误结构:
 * - { error: { message: string } }
 * - { message: string }
 * 纯文本时也做降级处理。
 */
export interface BackendError {
  error?: { message?: string };
  message?: string;
}

/**
 * 通用接口响应包装。部分接口直接返回 T，这里仅作为可选形态使用。
 */
export interface ApiResponse<T = unknown> {
  data?: T;
  message?: string;
  [key: string]: unknown;
}
