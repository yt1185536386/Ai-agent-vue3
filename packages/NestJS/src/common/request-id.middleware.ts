import { randomUUID } from 'crypto';
import type { Request, Response, NextFunction } from 'express';

/**
 * 全链路请求 ID:优先沿用上游传入的 X-Request-Id,否则生成 UUID。
 * 挂到 req.requestId 供服务层透传给 ai-service / model-gateway,
 * 并写入响应头方便前端/网关侧日志按 id 关联。
 */
export function requestIdMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
) {
  const incoming = req.headers['x-request-id'];
  const requestId =
    typeof incoming === 'string' && incoming.trim()
      ? incoming.trim().slice(0, 64)
      : randomUUID();
  (req as Request & { requestId?: string }).requestId = requestId;
  res.setHeader('X-Request-Id', requestId);
  next();
}
