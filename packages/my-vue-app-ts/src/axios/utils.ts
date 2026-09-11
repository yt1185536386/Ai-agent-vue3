import type { AxiosError } from "axios";
import { clearToken } from "../view/AgentMode/auth";
import type { BackendError } from "./types";

/**
 * 从可能包含 JSON 的文本中提取后端错误消息。
 */
export function extractMessageFromText(text: string): string | null {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;
  try {
    const parsed = JSON.parse(match[0]) as BackendError;
    return parsed.error?.message || parsed.message || null;
  } catch {
    return null;
  }
}

/**
 * 统一提取后端可读错误消息。
 */
export function extractErrorMessage(error: unknown): string {
  if (error instanceof Error && "response" in error) {
    const axiosError = error as AxiosError;
    const data = axiosError.response?.data;
    if (typeof data === "string") {
      return extractMessageFromText(data) || data || axiosError.message;
    }
    if (data && typeof data === "object") {
      const backend = data as BackendError;
      return (
        backend.error?.message ||
        backend.message ||
        axiosError.response?.statusText ||
        axiosError.message
      );
    }
    return axiosError.response?.statusText || axiosError.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

/**
 * 处理 401/403 未授权场景：清除 token 并跳转登录页。
 */
export function handleUnauthorized() {
  clearToken();
  const pathname = window.location.pathname;
  if (pathname !== "/login") {
    window.location.href = "/login";
  }
}
