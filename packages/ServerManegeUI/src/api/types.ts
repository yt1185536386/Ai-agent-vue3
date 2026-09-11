/** 各功能模块共用的实体类型定义 */

/** NestJS 用户(对齐 users 表;每个用户只属于一个部门) */
export interface UserItem {
  id: string; username: string; email?: string; displayName?: string
  isSuperAdmin: boolean; status: number
  jobLevel?: { id: number; name: string; rank: number } | null
  department?: { id: number; name: string } | null
  /** 部门内职位: MANAGER 经理 / DEPUTY 副经理 / LEADER 组长 / MEMBER 组员 */
  deptPosition: 'MANAGER' | 'DEPUTY' | 'LEADER' | 'MEMBER'
  lastLoginAt?: string; createdAt: string
}

export interface DeptNode {
  id: number; name: string; parentId?: number | null
  createdAt: string; updatedAt: string
}

export interface JobLevelItem {
  id: number; name: string; rank: number; builtin: boolean
  /** 职级所属部门 id(职级按部门划分) */
  departmentId: number
}

/** 可配置权限点 */
export interface PermPoint {
  id: number; code: string; module: string; action: string; name: string
}

/** 职级 × 权限点矩阵行 */
export interface JobLevelPermRow {
  jobLevel: { id: number; name: string; rank: number }
  codes: string[]
}

/** 按部门分组的职级权限矩阵 */
export interface DeptPermGroup {
  department: { id: number; name: string }
  levels: JobLevelPermRow[]
}

/** 个人权限配置 */
export interface UserPermConfig {
  user: UserItem
  overrides: Array<{ code: string; allowed: boolean }>
  inherited: string[]
  effective: string[]
}

export interface Channel {
  id: string; name: string; channelKey?: string; provider: string
  upstreamFormat: string; authType: string
  baseUrl: string; apiKey: string
  models: string; enableSearch: boolean; priority: number; status: number
  remark?: string; createdAt: string
}

export type ChannelPayload = Partial<Omit<Channel, 'models'>> & { models: string[] }

export interface Policy {
  id: string; name: string; type: 'RATE_LIMIT' | 'CIRCUIT_BREAKER'
  targetType: 'GLOBAL' | 'USER' | 'CHANNEL'; targetKey?: string
  qpm?: number; tpm?: number
  failureRateThreshold?: number; windowSeconds?: number; openSeconds?: number
  enabled: number; remark?: string
}

/** Java model-gateway 调用日志(唯一计量来源) */
export interface InvokeLog {
  id: string; userId: string; username: string
  channelId: string; channelName: string; model: string
  stream: boolean; status: number
  durationMs?: number
  promptTokens?: number; completionTokens?: number; totalTokens?: number
  errorMessage?: string; createdAt: string
}

export interface AggregateRow { groupKey: string; calls: number; tokens: number; errors: number }
export interface UserModelRow { username: string; model: string; calls: number; tokens: number }

/** 告警规则(Java model-gateway /api/alerts/rules) */
export interface AlertRule {
  id: string; name: string
  metric: 'CIRCUIT_OPEN' | 'RATE_LIMIT_HIT' | 'FAILURE_RATE' | 'AVG_LATENCY_MS' | 'ERROR_COUNT'
  targetType: 'GLOBAL' | 'CHANNEL'; targetKey?: string
  threshold?: number; windowSeconds?: number; cooldownSeconds?: number
  severity: 'INFO' | 'WARN' | 'CRITICAL'
  enabled: number; remark?: string; createdAt?: string
}

/** 告警触发记录(/api/alerts/records) */
export interface AlertRecord {
  id: string; ruleId: string; ruleName: string
  severity: 'INFO' | 'WARN' | 'CRITICAL'; metric: string
  targetKey: string; metricValue?: number; message: string
  status: 'FIRING' | 'RESOLVED'; readFlag: number
  createdAt: string; resolvedAt?: string
}

export interface Overview {
  summary: {
    totalCalls: number; totalTokens: number
    callsPerMinute: number; tokensPerMinute: number
    errorRate: number; totalErrors: number
  }
  byUser: AggregateRow[]
  byModel: AggregateRow[]
  byChannel: AggregateRow[]
  trend: AggregateRow[]
  userModel: UserModelRow[]
}
