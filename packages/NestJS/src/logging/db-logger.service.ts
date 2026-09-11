import { ConsoleLogger, Injectable } from '@nestjs/common';
import { DataSource } from 'typeorm';
import { LogNestjsEntity } from './log-nestjs.entity';

interface BufferedLog {
  level: string;
  context: string;
  message: string;
}

// 全局运行日志:控制台输出保持 NestJS 默认行为不变,同时批量落库到 log_nestjs 表。
// 关键约束:落库失败只写 stderr,绝不向上抛——日志系统不能拖垮业务,更不能递归自我记录。
@Injectable()
export class DbLoggerService extends ConsoleLogger {
  private static readonly FLUSH_INTERVAL_MS = 2000;
  private static readonly MAX_BATCH = 200;

  private buffer: BufferedLog[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(private readonly dataSource: DataSource) {
    super();
    this.setContext('App');
  }

  onApplicationBootstrap() {
    this.timer = setInterval(() => this.flush(), DbLoggerService.FLUSH_INTERVAL_MS);
    // unref:这个定时器不能阻止进程退出
    (this.timer as { unref?: () => void }).unref?.();
  }

  onApplicationShutdown() {
    if (this.timer) clearInterval(this.timer);
    this.flush();
  }

  log(message: unknown, context?: string) {
    this.capture('log', message, context);
    super.log(message, context);
  }

  warn(message: unknown, context?: string) {
    this.capture('warn', message, context);
    super.warn(message, context);
  }

  debug(message: unknown, context?: string) {
    this.capture('debug', message, context);
    super.debug(message, context);
  }

  verbose(message: unknown, context?: string) {
    this.capture('verbose', message, context);
    super.verbose(message, context);
  }

  error(message: unknown, trace?: string, context?: string) {
    this.capture('error', trace ? `${message}\n${trace}` : message, context);
    super.error(message, trace, context);
  }

  private capture(level: string, message: unknown, context?: string) {
    this.buffer.push({
      level,
      context: context ?? 'App',
      message: typeof message === 'string' ? message : JSON.stringify(message),
    });
    if (this.buffer.length >= DbLoggerService.MAX_BATCH) this.flush();
  }

  private flush() {
    if (this.buffer.length === 0) return;
    const batch = this.buffer.splice(0, this.buffer.length);
    this.dataSource
      .createQueryBuilder()
      .insert()
      .into(LogNestjsEntity)
      .values(batch.map((b) => ({ ...b, meta: null })))
      .execute()
      .catch((err: Error) => {
        // 直接写 stderr:再走 logger 会递归回到本服务
        process.stderr.write(
          `[DbLogger] 运行日志落库失败(${err?.message ?? err}),丢弃 ${batch.length} 条\n`,
        );
      });
  }
}
