import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  ManyToOne,
  JoinColumn,
  Unique,
} from 'typeorm';
import { JobLevel } from './job-level.entity';
import { Permission } from './permission.entity';

/** 职级权限绑定: 同一职级的用户批量继承该职级绑定的权限点 */
@Entity('job_level_permissions')
@Unique(['jobLevelId', 'permissionId'])
export class JobLevelPermission {
  @PrimaryGeneratedColumn()
  id: number;

  @ManyToOne(() => JobLevel, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'jobLevelId' })
  jobLevel: JobLevel;

  @Column({ type: 'int' })
  jobLevelId: number;

  @ManyToOne(() => Permission, { onDelete: 'CASCADE', eager: true })
  @JoinColumn({ name: 'permissionId' })
  permission: Permission;

  @Column({ type: 'int' })
  permissionId: number;
}
