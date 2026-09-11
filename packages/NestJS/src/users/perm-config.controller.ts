import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Put,
  Req,
} from '@nestjs/common';
import type { Request } from 'express';
import { RequirePerm } from '../auth/permissions.decorator';
import { PERM_AUTH } from './permission-codes';
import { User } from './users.entity';
import { UsersService } from './users.service';
import { SetJobLevelPermsDto, SetUserPermsDto } from './users.dto';

type AuthedRequest = Request & { currentUser: User };

/**
 * 权限维护(两个维度): 职级批量绑定 + 个人单独绑定(逐项覆盖,个人优先)。
 * 整个模块对登录用户开放(PERM_AUTH),细粒度校验全部在服务层:
 * 超管任意;部门经理全权管理本部门子树(职级绑定 + 成员个人绑定);
 * 其余用户须持有「部门成员管理」权限点且职级严格高于目标(个人绑定)。
 * 超管本人(eric)的权限不可被任何人修改。
 */
@Controller('v1/perm-config')
@RequirePerm(PERM_AUTH)
export class PermConfigController {
  constructor(private readonly usersService: UsersService) {}

  /** 全部可配置权限点(字典) */
  @Get('points')
  points() {
    return this.usersService.listPermPoints();
  }

  /** 职级 × 权限点矩阵(按部门分组;超管全量,经理限本部门子树) */
  @Get('job-levels')
  jobLevelMatrix(@Req() req: AuthedRequest) {
    return this.usersService.jobLevelPermMatrix(req.currentUser);
  }

  /** 职级批量绑定: 全量覆盖该职级的权限点集合 */
  @Put('job-levels/:id')
  setJobLevelPerms(
    @Req() req: AuthedRequest,
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: SetJobLevelPermsDto,
  ) {
    return this.usersService.setJobLevelPerms(req.currentUser, id, dto);
  }

  /** 个人权限配置: 个人覆盖项 + 职级继承项 + 有效结果 */
  @Get('users/:userId')
  userConfig(@Req() req: AuthedRequest, @Param('userId') userId: string) {
    return this.usersService.userPermConfig(req.currentUser, userId);
  }

  /** 个人单独绑定: 全量覆盖;allowed 为 null 的项删除(回到继承职级) */
  @Put('users/:userId')
  setUserPerms(
    @Req() req: AuthedRequest,
    @Param('userId') userId: string,
    @Body() dto: SetUserPermsDto,
  ) {
    return this.usersService.setUserPerms(req.currentUser, userId, dto);
  }
}
