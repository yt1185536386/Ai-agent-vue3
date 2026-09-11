import axios, { type AxiosResponse } from "axios";
import { getToken } from "../view/AgentMode/auth";
import { extractErrorMessage, handleUnauthorized } from "./utils";
import type { RequestConfig } from "./types";

export const request = axios.create({
  baseURL: "/api",
  timeout: 60_000,
  headers: {
    Accept: "application/json",
  },
});

// 请求拦截器：注入 token；FormData 请求不覆盖 Content-Type
request.interceptors.request.use((config) => {
  if (config.skipAuth) return config;

  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：仅 401 跳转登录；403(权限不足)由页面展示错误信息
request.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    if (error.response?.status === 401) {
      handleUnauthorized();
    }
    return Promise.reject(error);
  },
);

export async function get<T = unknown>(url: string, config?: RequestConfig): Promise<T> {
  const { data } = await request.get<T>(url, config);
  return data;
}

export async function post<T = unknown>(
  url: string,
  body?: unknown,
  config?: RequestConfig,
): Promise<T> {
  const { data } = await request.post<T>(url, body, config);
  return data;
}

export async function put<T = unknown>(
  url: string,
  body?: unknown,
  config?: RequestConfig,
): Promise<T> {
  const { data } = await request.put<T>(url, body, config);
  return data;
}

export async function patch<T = unknown>(
  url: string,
  body?: unknown,
  config?: RequestConfig,
): Promise<T> {
  const { data } = await request.patch<T>(url, body, config);
  return data;
}

export async function del<T = unknown>(url: string, config?: RequestConfig): Promise<T> {
  const { data } = await request.delete<T>(url, config);
  return data;
}

export { extractErrorMessage };
export default request;
