import { NestFactory } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import { ValidationPipe } from '@nestjs/common';
import * as path from 'path';
import { config as dotenvConfig } from 'dotenv';
import { AppModule } from './app.module';
import { DbLoggerService } from './logging/db-logger.service';
import { requestIdMiddleware } from './common/request-id.middleware';

// 无论从哪个 cwd 启动,都读取 NestJS 目录下的 .env
dotenvConfig({ path: path.resolve(__dirname, '../.env') });

async function bootstrap() {
  // 关闭默认 bodyParser(默认 JSON 上限 100KB,装不下 base64 图片)
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    bodyParser: false,
  });
  app.useBodyParser('json', { limit: '50mb' });
  app.useBodyParser('urlencoded', { limit: '50mb', extended: true });

  // 全链路请求 ID:后续转发链路(NestJS → ai-service → model-gateway)按它关联日志
  app.use(requestIdMiddleware);

  // CORS 白名单:CORS_ORIGINS 逗号分隔;未配置时默认只放行本地开发端口,
  // 生产环境务必显式配置(原先 origin:true 等于全站放开带凭证跨域)
  const corsOrigins = (process.env.CORS_ORIGINS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  app.enableCors({
    origin:
      corsOrigins.length > 0
        ? corsOrigins
        : ['http://localhost:6012', 'http://localhost:6013'],
    credentials: true,
  });

  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
  // 优雅停机:收到 SIGTERM 后停止接新请求,存量请求处理完再退出
  app.enableShutdownHooks();
  await app.listen(process.env.PORT ?? 6011);
}
bootstrap();
