import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
} from 'typeorm';

@Entity('job_levels')
export class JobLevel {
  @PrimaryGeneratedColumn()
  id: number;

  /** 职级名称,如 高级(部门内允许重复,同名时按层级区分) */
  @Column({ length: 50 })
  name: string;

  /** 层级数值,越小级别越高(允许重复,同级视为并列) */
  @Column({ type: 'int' })
  rank: number;

  /** 所属部门 id: 职级按部门划分,每个部门一套自己的职级 */
  @Column({ type: 'int', nullable: true })
  departmentId: number;

  /** 内置职级(种子数据),仅作标识不阻止删除 */
  @Column({ type: 'boolean', default: false })
  builtin: boolean;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
