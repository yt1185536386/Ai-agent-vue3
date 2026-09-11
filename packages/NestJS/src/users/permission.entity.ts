import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
} from 'typeorm';

/** 按钮级权限(查看/新增/编辑/删除/导出) */
@Entity('permissions')
export class Permission {
  @PrimaryGeneratedColumn()
  id: number;

  /** 权限码,如 user:view / user:create / user:export */
  @Column({ unique: true, length: 64 })
  code: string;

  /** 所属模块,如 user / joblevel / dept / audit / asset */
  @Column({ length: 32 })
  module: string;

  /** 动作: 查看/新增/编辑/删除/导出/管理 */
  @Column({ length: 16 })
  action: string;

  /** 中文按钮名,如 查看用户 */
  @Column({ length: 64 })
  name: string;

  @CreateDateColumn()
  createdAt: Date;
}
