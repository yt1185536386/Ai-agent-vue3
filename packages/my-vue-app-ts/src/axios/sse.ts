import { getToken } from "../view/AgentMode/auth";
import { extractErrorMessage, handleUnauthorized } from "./utils";

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface FetchSSEOptions {
  url: string;
  body: unknown;
  signal?: AbortSignal;
  onEvent?: (event: SSEEvent) => void;
  onError?: (message: string) => void;
}

/**
 * 解析 SSE 帧:
 * 格式 `event: <type>\ndata: <json>\n\n`，支持多 data 行拼接。
 */
export function parseSSE(raw: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const blocks = raw.split("\n\n");
  for (const block of blocks) {
    if (!block.trim()) continue;
    let event = "message";
    const datas: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) datas.push(line.slice(5).trim());
    }
    const dataStr = datas.join("\n");
    if (dataStr === "[DONE]") continue;
    let data: Record<string, unknown> = {};
    try {
      data = JSON.parse(dataStr) as Record<string, unknown>;
    } catch {
      data = { raw: dataStr };
    }
    events.push({ event, data });
  }
  return events;
}

/**
 * 基于原生 fetch 的 SSE 请求封装。
 * 复用与 axios 实例相同的 token 注入与 401 处理逻辑，
 * 支持 AbortController 取消请求。
 */
export async function fetchSSE(options: FetchSSEOptions): Promise<void> {
  const { url, body, signal, onEvent, onError } = options;

  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    onError?.(extractErrorMessage(err));
    throw err;
  }

  if (!res.ok) {
    // 仅 401 视为登录失效;403 为权限不足,展示错误信息即可
    if (res.status === 401) {
      handleUnauthorized();
      throw new Error("登录已失效，请重新登录");
    }
    const text = await res.text();
    const message = extractErrorMessage(text) || text || `HTTP ${res.status}`;
    throw new Error(message);
  }

  if (!res.body) {
    throw new Error("响应体为空");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    if (!parts.length) continue;

    for (const { event, data } of parseSSE(parts.join("\n\n"))) {
      if (event === "error") {
        const message = typeof data.message === "string" ? data.message : "服务端错误";
        onError?.(message);
        throw new Error(message);
      }
      onEvent?.({ event, data });
    }
  }
}
