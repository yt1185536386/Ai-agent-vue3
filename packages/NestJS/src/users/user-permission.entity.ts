import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Unique,
} from 'typeorm';
import { Permission } from './permission.entity';

/**
 * 个人权限绑定: 逐权限点覆盖职级绑定。
 * 某权限点有记录 → 以 allowed 为准(允许/拒绝);无记录 → 继承职级绑定。
 */
@Entity('user_permissions')
@Unique(['userId', 'permissionId'])
export class UserPermissionGrant {
  @PrimaryGeneratedColumn()
  id: number;

  /** users.id(uuid) */
  @Column({ length: 36 })
  userId: string;

  @ManyToOne(() => Permission, { onDelete: 'CASCADE', eager: true })
  @JoinColumn({ name: 'permissionId' })
  permission: Permission;

  @Column({ type: 'int' })
  permissionId: number;

  /** true 授予 / false 拒绝(拒绝用于收掉职级继承来的权限) */
  @Column({ type: 'boolean' })
  allowed: boolean;

  @CreateDateColumn()
  createdAt: Date;
}
