import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

// 运行日志表(应用名 = nestjs),由 DbLoggerService 批量写入。
// 开发环境靠 DB_SYNCHRONIZE 自动建表;生产环境用 sql/log_tables.sql 预建,
// 与 log_ai_service(Python)、log_model_gateway(Java) 保持同构。
@Entity('log_nestjs')
export class LogNestjsEntity {
  @PrimaryGeneratedColumn({ type: 'bigint' })
  id: string;

  @Column({ type: 'varchar', length: 16, comment: 'log/warn/error/debug/verbose' })
  level: string;

  @Column({ type: 'varchar', length: 100, nullable: true, comment: '日志上下文(模块名)' })
  context: string | null;

  @Column({ type: 'text', comment: '日志正文(含异常堆栈)' })
  message: string;

  @Column({ type: 'json', nullable: true, comment: '结构化附加信息(requestId 等,预留)' })
  meta: Record<string, unknown> | null;

  // 列名对齐另外两张日志表(dblog.py/MysqlLogAppender 均写 created_at),便于统一查询
  @CreateDateColumn({ type: 'datetime', precision: 6, name: 'created_at' })
  createdAt: Date;
}
