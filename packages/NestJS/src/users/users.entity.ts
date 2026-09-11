import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
} from 'typeorm';
import { JobLevel } from './job-level.entity';
import { Department } from './department.entity';

export enum UserStatus {
  ACTIVE = 1,
  DISABLED = 0,
}

/** 部门内职位: 经理(每部门限1)/副经理(限2)/组长(不限)/组员 */
export enum DeptPosition {
  MANAGER = 'MANAGER',
  DEPUTY = 'DEPUTY',
  LEADER = 'LEADER',
  MEMBER = 'MEMBER',
}

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** 登录用户名(唯一) */
  @Column({ unique: true, length: 64 })
  username: string;

  /** bcrypt 密码哈希 */
  @Column({ length: 255 })
  passwordHash: string;

  /** 邮箱(唯一,可选) */
  @Column({ unique: true, length: 120, nullable: true })
  email?: string;

  /** 显示昵称 */
  @Column({ length: 100, nullable: true })
  displayName?: string;

  /** 头像 URL */
  @Column({ length: 255, nullable: true })
  avatar?: string;

  /** 超级管理员标记: 拥有全部权限点且不可被任何人管理 */
  @Column({ type: 'boolean', default: false })
  isSuperAdmin: boolean;

  /** 职级(权限绑定维度之一;上下级管理规则的层级依据) */
  @ManyToOne(() => JobLevel, { nullable: true, eager: true, onDelete: 'SET NULL' })
  @JoinColumn({ name: 'jobLevelId' })
  jobLevel?: JobLevel | null;

  /** 所属部门(每个用户只属于一个部门;ABAC 数据隔离依据) */
  @ManyToOne(() => Department, { nullable: true, eager: true, onDelete: 'SET NULL' })
  @JoinColumn({ name: 'departmentId' })
  department?: Department | null;

  /** 部门内职位: MANAGER 经理 / DEPUTY 副经理 / LEADER 组长 / MEMBER 组员 */
  @Column({ type: 'varchar', length: 20, default: DeptPosition.MEMBER })
  deptPosition: DeptPosition;

  /** 状态: 1 启用 / 0 禁用 */
  @Column({ type: 'tinyint', default: UserStatus.ACTIVE })
  status: UserStatus;

  /** 最后登录时间 */
  @Column({ type: 'datetime', nullable: true })
  lastLoginAt?: Date;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
