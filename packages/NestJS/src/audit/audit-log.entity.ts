import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
} from 'typeorm';

/** 全链路审计日志: 人员与权限相关操作(含 HITL 审批结果) */
@Entity('audit_logs')
@Index(['operatorId', 'createdAt'])
@Index(['targetId', 'createdAt'])
export class AuditLog {
  @PrimaryGeneratedColumn()
  id: number;

  /** 操作者 id / 名称快照 */
  @Column({ length: 36 })
  operatorId: string;

  @Column({ length: 100 })
  operatorName: string;

  /** 动作,如 user.create / user.adjust_job_level / temp_perm.grant */
  @Column({ length: 64 })
  action: string;

  /** 目标类型: user / joblevel / department / temp_permission */
  @Column({ length: 32 })
  targetType: string;

  @Column({ length: 64 })
  targetId: string;

  /** 目标名称快照 */
  @Column({ length: 100 })
  targetName: string;

  /** 变更明细(before→after、槽位、原因等) */
  @Column({ type: 'json', nullable: true })
  detail?: Record<string, unknown> | null;

  /** HITL 结果: auto 常规直接执行 / approved 审批通过 / rejected 审批拒绝 */
  @Column({ length: 16 })
  outcome: 'auto' | 'approved' | 'rejected';

  @CreateDateColumn({ type: 'datetime', precision: 6 })
  createdAt: Date;
}
