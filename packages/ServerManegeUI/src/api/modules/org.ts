import http from '../http'
import type {
  DeptNode,
  DeptPermGroup,
  JobLevelItem,
  PermPoint,
  UserItem,
  UserPermConfig,
} from '../types'

/**
 * 组织与权限(NestJS 业务网关, /nestjs 代理,原生响应无统一包装)。
 * 用户/部门写操作的规则引擎(上级管下级、职位名额、部门范围)只在 NestJS 实现。
 */

/** 用户管理(需 dept:member 权限点、部门经理或超管) */
export const orgUserApi = {
  list: () => http.get<UserItem[]>('/nestjs/v1/users'),
  create: (data: Record<string, unknown>) => http.post('/nestjs/v1/users', data),
  update: (id: string, data: Record<string, unknown>) => http.patch(`/nestjs/v1/users/${id}`, data),
  remove: (id: string) => http.delete(`/nestjs/v1/users/${id}`),
}

/** 当前用户有效权限(任何登录用户) */
export const myPermApi = {
  mine: () => http.get<{ isSuperAdmin: boolean; permissions: string[] }>('/nestjs/v1/users/me/permissions'),
}

/** 部门管理(写操作需 dept:info 权限点、部门经理或超管) */
export const deptApi = {
  list: () => http.get<DeptNode[]>('/nestjs/v1/departments'),
  create: (data: { name: string; parentId?: number | null; confirm: true }) =>
    http.post('/nestjs/v1/departments', data),
  update: (id: number, data: { name?: string; parentId?: number; confirm: true }) =>
    http.patch(`/nestjs/v1/departments/${id}`, data),
  remove: (id: number) => http.delete(`/nestjs/v1/departments/${id}`),
}

/** 职级(按部门划分): 所有登录用户可查;写操作需超管或部门经理 */
export const jobLevelApi = {
  list: (departmentId?: number) => http.get<JobLevelItem[]>(
    '/nestjs/v1/job-levels' + (departmentId != null ? `?departmentId=${departmentId}` : ''),
  ),
  create: (data: { name: string; rank: number; departmentId: number; confirm: true }) =>
    http.post('/nestjs/v1/job-levels', data),
  update: (id: number, data: { name?: string; rank?: number; confirm: true }) =>
    http.patch(`/nestjs/v1/job-levels/${id}`, data),
  remove: (id: number) => http.delete(`/nestjs/v1/job-levels/${id}`),
}

/** 权限维护: 职级批量绑定需超管或部门经理;个人单独绑定需高职级或部门经理(超管本人不可修改) */
export const permConfigApi = {
  points: () => http.get<PermPoint[]>('/nestjs/v1/perm-config/points'),
  jobLevelMatrix: () => http.get<DeptPermGroup[]>('/nestjs/v1/perm-config/job-levels'),
  setJobLevelPerms: (id: number, codes: string[]) =>
    http.put(`/nestjs/v1/perm-config/job-levels/${id}`, { codes }),
  userConfig: (userId: string) => http.get<UserPermConfig>(`/nestjs/v1/perm-config/users/${userId}`),
  setUserPerms: (userId: string, overrides: Array<{ code: string; allowed: boolean | null }>) =>
    http.put(`/nestjs/v1/perm-config/users/${userId}`, { overrides }),
}
