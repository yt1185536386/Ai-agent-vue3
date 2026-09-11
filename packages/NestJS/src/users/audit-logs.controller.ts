import { Controller, Get, Query } from '@nestjs/common';
import { RequirePerm } from '../auth/permissions.decorator';
import { PERM_SUPER } from './permission-codes';
import { UsersService } from './users.service';

@Controller('v1/audit-logs')
export class AuditLogsController {
  constructor(private readonly usersService: UsersService) {}

  /** 审计日志: 仅超级管理员,全量分页 */
  @Get()
  @RequirePerm(PERM_SUPER)
  query(
    @Query('keyword') keyword?: string,
    @Query('days') days?: string,
    @Query('page') page?: string,
  ) {
    return this.usersService.queryAuditLogs({
      keyword,
      days: days ? Number(days) : undefined,
      page: page ? Number(page) : undefined,
    });
  }
}
