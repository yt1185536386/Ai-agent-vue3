import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { UsersService } from '../users/users.service';
import { PERM_AUTH, PERM_SUPER } from '../users/permission-codes';
import { REQUIRE_PERM_KEY } from './permissions.decorator';

/**
 * 全局权限守卫(在 JwtAuthGuard 之后执行)。
 * 用户与有效权限码经 UsersService 的 30s 快照缓存加载
 * (原先每请求 ~4 次查库);权限/禁用变更由写操作主动失效缓存,立即生效。
 * 路由无 @RequirePerm 元数据时只做「用户加载 + 状态校验」;
 * 有元数据时:超管全通,'super' 仅超管,其余按有效权限码
 * (个人绑定逐项覆盖职级绑定)校验。
 */
@Injectable()
export class PermissionGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    private readonly usersService: UsersService,
  ) {}

  async canActivate(ctx: ExecutionContext): Promise<boolean> {
    const req = ctx.switchToHttp().getRequest();
    const payload = req.user as { userId?: string } | undefined;
    // @Public 路由:JwtAuthGuard 已放行,无 JWT payload
    if (!payload?.userId) return true;

    const ctxData = await this.usersService.loadAuthContext(payload.userId);
    if (!ctxData) {
      throw new UnauthorizedException('用户不存在');
    }
    const { user, codes } = ctxData;
    if (user.status !== 1) {
      throw new ForbiddenException('账号已被禁用');
    }
    req.currentUser = user;

    const required = this.reflector.getAllAndOverride<string>(
      REQUIRE_PERM_KEY,
      [ctx.getHandler(), ctx.getClass()],
    );
    if (!required) return true;
    // 'auth': 任意登录用户,细粒度校验由服务层完成
    if (required === PERM_AUTH) return true;
    if (user.isSuperAdmin) return true;
    if (required === PERM_SUPER) {
      throw new ForbiddenException('仅超级管理员可执行该操作');
    }
    if (!codes.has(required)) {
      throw new ForbiddenException('没有操作权限');
    }
    return true;
  }
}
