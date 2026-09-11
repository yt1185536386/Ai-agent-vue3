import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  Param,
  Patch,
  Post,
  Req,
} from '@nestjs/common';
import type { Request } from 'express';
import { RequirePerm } from '../auth/permissions.decorator';
import { User } from './users.entity';
import { AuditOutcome, UsersService } from './users.service';
import { CreateUserDto, UpdateUserDto } from './users.dto';

/** PermissionGuard 校验通过后注入的完整用户实体 */
type AuthedRequest = Request & { currentUser: User };

/** HITL 审批结果: ai-service 审批通过后带 X-HITL: approved */
function outcomeOf(req: Request): AuditOutcome {
  return req.headers['x-hitl'] === 'approved' ? 'approved' : 'auto';
}

@Controller('v1/users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get('me')
  me(@Req() req: AuthedRequest) {
    return this.usersService.toSafe(req.currentUser);
  }

  /** 当前用户有效权限: 个人绑定逐项覆盖职级绑定,超管全通 */
  @Get('me/permissions')
  myPermissions(@Req() req: AuthedRequest) {
    return this.usersService.effectivePermissions(req.currentUser.id);
  }

  /** 用户列表: 超管全量;部门成员管理权限持有者限本部门子树(均含自己) */
  @Get()
  @RequirePerm('dept:member')
  list(@Req() req: AuthedRequest) {
    return this.usersService.listVisible(req.currentUser);
  }

  /** 创建用户: 需部门成员管理权限;非超管限本部门子树 + 职级须低于自己 */
  @Post()
  @RequirePerm('dept:member')
  create(@Req() req: AuthedRequest, @Body() dto: CreateUserDto) {
    return this.usersService.adminCreate(req.currentUser, dto, outcomeOf(req));
  }

  /** 更新用户: 资料/状态/重置密码/职级(上级调下级)/转岗/部门职位 */
  @Patch(':id')
  @RequirePerm('dept:member')
  update(
    @Req() req: AuthedRequest,
    @Param('id') id: string,
    @Body() dto: UpdateUserDto,
  ) {
    return this.usersService.adminUpdate(req.currentUser, id, dto, outcomeOf(req));
  }

  @Delete(':id')
  @RequirePerm('dept:member')
  @HttpCode(204)
  async remove(@Req() req: AuthedRequest, @Param('id') id: string) {
    await this.usersService.adminRemove(req.currentUser, id, outcomeOf(req));
  }
}
