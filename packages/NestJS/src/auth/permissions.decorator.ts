import { SetMetadata } from '@nestjs/common';

export const REQUIRE_PERM_KEY = 'requirePerm';

/**
 * 权限码元数据,如 @RequirePerm('dept:member')。
 * 特殊值 'super' 表示仅超级管理员;其余为 permissions 表中的权限码
 * (有效权限 = 个人绑定逐项覆盖职级绑定,超管全通,由 PermissionGuard 校验)。
 */
export const RequirePerm = (code: string) =>
  SetMetadata(REQUIRE_PERM_KEY, code);
