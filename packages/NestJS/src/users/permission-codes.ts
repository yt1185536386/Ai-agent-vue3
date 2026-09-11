/** 可配置权限点: [code, module, action, 中文名] */
export const PERMISSION_SEEDS: Array<[string, string, string, string]> = [
  ['dept:member', 'dept', '管理', '部门成员管理'],
  ['dept:info', 'dept', '管理', '部门信息维护'],
  ['dept:knowledge', 'dept', '管理', '部门知识库管理'],
  ['log:view', 'log', '查看', '调用日志查看'],
  ['policy:manage', 'policy', '管理', '限流熔断管理'],
  ['prompt:manage', 'prompt', '管理', 'Prompt 模板管理'],
  ['prompt:view', 'prompt', '查看', 'Prompt 监控查看'],
  ['ctx:view', 'ctx', '查看', 'Context 监控查看'],
];

export const ALL_PERM_CODES: string[] = PERMISSION_SEEDS.map((p) => p[0]);

/** @RequirePerm 的特殊值: 仅超级管理员 */
export const PERM_SUPER = 'super';

/** @RequirePerm 的特殊值: 任意登录用户(细粒度校验下沉到服务层) */
export const PERM_AUTH = 'auth';
