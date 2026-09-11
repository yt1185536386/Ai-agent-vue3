import { Controller, Get, HttpException, HttpStatus, SetMetadata } from '@nestjs/common';
import { DataSource } from 'typeorm';
import { AppService } from './app.service';

@Controller()
@SetMetadata('isPublic', true)
export class AppController {
  constructor(
    private readonly appService: AppService,
    private readonly dataSource: DataSource,
  ) {}

  @Get()
  getHello(): string {
    return this.appService.getHello();
  }

  /**
   * 健康检查(存活 + 依赖探测):启动脚本/负载均衡按它判断"活着且能用"。
   * DB 不通时返回 503,便于编排系统摘除实例。
   */
  @Get('health')
  async health() {
    const detail: Record<string, string> = {};
    let ok = true;
    try {
      await this.dataSource.query('SELECT 1');
      detail.db = 'up';
    } catch {
      detail.db = 'down';
      ok = false;
    }
    const body = {
      status: ok ? 'ok' : 'degraded',
      detail,
      time: new Date().toISOString(),
    };
    if (!ok) {
      throw new HttpException(body, HttpStatus.SERVICE_UNAVAILABLE);
    }
    return body;
  }
}
