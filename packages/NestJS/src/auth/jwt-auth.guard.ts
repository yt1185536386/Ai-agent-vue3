import {
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Reflector } from '@nestjs/core';
import { AuthGuard } from '@nestjs/passport';
import { timingSafeEqual } from 'crypto';
import { IS_PUBLIC_KEY } from './public.decorator';

/** 常量时间字符串比较,避免逐字符比较的时序侧信道 */
function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  return ba.length === bb.length && timingSafeEqual(ba, bb);
}

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  constructor(
    private reflector: Reflector,
    private config: ConfigService,
  ) {
    super();
  }

  canActivate(context: ExecutionContext) {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) {
      return true;
    }
    // 内部服务(ai-service)模拟身份调用:共享密钥 + X-User-Id,
    // 跳过 JWT,由 PermissionGuard 从 DB 加载该用户并做权限校验
    const req = context.switchToHttp().getRequest();
    const serviceKey = req.headers['x-service-key'];
    const impersonateId = req.headers['x-user-id'];
    const configured = this.config.get<string>('NESTJS_SERVICE_KEY');
    if (
      configured &&
      typeof serviceKey === 'string' &&
      serviceKey &&
      typeof impersonateId === 'string' &&
      impersonateId &&
      safeEqual(serviceKey, configured)
    ) {
      req.user = { userId: impersonateId, username: '' };
      return true;
    }
    return super.canActivate(context);
  }

  handleRequest(err: any, user: any) {
    if (err || !user) {
      throw err || new UnauthorizedException('未登录或 Token 无效');
    }
    return user;
  }
}
