import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  Param,
  ParseIntPipe,
  Patch,
  Post,
  Query,
  Req,
} from '@nestjs/common';
import type { Request } from 'express';
import { RequirePerm } from '../auth/permissions.decorator';
import { PERM_AUTH } from './permission-codes';
import { User } from './users.entity';
import { AuditOutcome, UsersService } from './users.service';
import { CreateJobLevelDto, UpdateJobLevelDto } from './users.dto';

type AuthedRequest = Request & { currentUser: User };

function outcomeOf(req: Request): AuditOutcome {
  return req.headers['x-hitl'] === 'approved' ? 'approved' : 'auto';
}

/**
 * 职级(按部门划分): 查询对所有登录用户开放(下拉框需要);
 * 写操作由服务层校验 —— 超管任意部门,部门经理限本部门子树。
 */
@Controller('v1/job-levels')
export class JobLevelsController {
  constructor(private readonly usersService: UsersService) {}

  /** 职级列表: 所有登录用户可查;可按部门过滤 */
  @Get()
  list(@Query('departmentId') departmentId?: string) {
    const deptId = departmentId != null ? Number(departmentId) : undefined;
    return this.usersService.listJobLevels(
      deptId != null && Number.isInteger(deptId) ? deptId : undefined,
    );
  }

  @Post()
  @RequirePerm(PERM_AUTH)
  create(@Req() req: AuthedRequest, @Body() dto: CreateJobLevelDto) {
    return this.usersService.createJobLevel(req.currentUser, dto, outcomeOf(req));
  }

  @Patch(':id')
  @RequirePerm(PERM_AUTH)
  update(
    @Req() req: AuthedRequest,
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateJobLevelDto,
  ) {
    return this.usersService.updateJobLevel(req.currentUser, id, dto, outcomeOf(req));
  }

  @Delete(':id')
  @RequirePerm(PERM_AUTH)
  @HttpCode(204)
  async remove(@Req() req: AuthedRequest, @Param('id', ParseIntPipe) id: number) {
    await this.usersService.removeJobLevel(req.currentUser, id, outcomeOf(req));
  }
}
