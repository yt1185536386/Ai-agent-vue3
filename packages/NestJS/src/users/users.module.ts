import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { User } from './users.entity';
import { JobLevel } from './job-level.entity';
import { Department } from './department.entity';
import { Permission } from './permission.entity';
import { JobLevelPermission } from './job-level-permission.entity';
import { UserPermissionGrant } from './user-permission.entity';
import { AuditLog } from '../audit/audit-log.entity';
import { UsersService } from './users.service';
import { UsersController } from './users.controller';
import { JobLevelsController } from './job-levels.controller';
import { DepartmentsController } from './departments.controller';
import { AuditLogsController } from './audit-logs.controller';
import { PermConfigController } from './perm-config.controller';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      User,
      JobLevel,
      Department,
      Permission,
      JobLevelPermission,
      UserPermissionGrant,
      AuditLog,
    ]),
  ],
  providers: [UsersService],
  controllers: [
    UsersController,
    JobLevelsController,
    DepartmentsController,
    AuditLogsController,
    PermConfigController,
  ],
  exports: [UsersService],
})
export class UsersModule {}
