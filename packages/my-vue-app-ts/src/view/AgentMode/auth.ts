const TOKEN_KEY = "eric-agent-token";

export interface AuthInfo {
  token: string;
  userId: string;
  username: string;
  /** 超级管理员标记(旧 token 兜底为 false) */
  isSuperAdmin: boolean;
  jobLevelRank: number | null;
  jobLevelName: string | null;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function parseJwt(token: string): any {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function loadAuth(): AuthInfo | null {
  const token = getToken();
  if (!token) return null;
  const payload = parseJwt(token);
  if (!payload?.sub || !payload?.username) {
    clearToken();
    return null;
  }
  return {
    token,
    userId: payload.sub,
    username: payload.username,
    isSuperAdmin: payload.isSuperAdmin === true,
    jobLevelRank: payload.jobLevelRank ?? null,
    jobLevelName: payload.jobLevelName ?? null,
  };
}

export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
