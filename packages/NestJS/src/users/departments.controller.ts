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
  Req,
} from '@nestjs/common';
import type { Request } from 'express';
import { RequirePerm } from '../auth/permissions.decorator';
import { User } from './users.entity';
import { AuditOutcome, UsersService } from './users.service';
import { CreateDepartmentDto, UpdateDepartmentDto } from './users.dto';

type AuthedRequest = Request & { currentUser: User };

function outcomeOf(req: Request): AuditOutcome {
  return req.headers['x-hitl'] === 'approved' ? 'approved' : 'auto';
}

@Controller('v1/departments')
export class DepartmentsController {
  constructor(private readonly usersService: UsersService) {}

  /** 部门树: 所有登录用户可查 */
  @Get()
  list() {
    return this.usersService.listDepartments();
  }

  /** 以下结构变更需「部门信息维护」权限 */
  @Post()
  @RequirePerm('dept:info')
  create(@Req() req: AuthedRequest, @Body() dto: CreateDepartmentDto) {
    return this.usersService.createDepartment(req.currentUser, dto, outcomeOf(req));
  }

  @Patch(':id')
  @RequirePerm('dept:info')
  update(
    @Req() req: AuthedRequest,
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateDepartmentDto,
  ) {
    return this.usersService.updateDepartment(req.currentUser, id, dto, outcomeOf(req));
  }

  @Delete(':id')
  @RequirePerm('dept:info')
  @HttpCode(204)
  async remove(@Req() req: AuthedRequest, @Param('id', ParseIntPipe) id: number) {
    await this.usersService.removeDepartment(req.currentUser, id, outcomeOf(req));
  }
}
