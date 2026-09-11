import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

/**
 * 每个用户的聊天偏好(模型来源 + 当前模型)。
 * 一人一行的稀疏表:首次访问时按环境变量默认值创建。
 */
@Entity('user_chat_settings')
export class UserChatSetting {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  /** 关联 users.id,一人一行 */
  @Column({ length: 64 })
  @Index({ unique: true })
  userId: string;

  /** 当前模型来源 key(company / bailian 等) */
  @Column({ length: 32 })
  provider: string;

  /** 当前生效的模型名 */
  @Column({ length: 128 })
  model: string;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
}
