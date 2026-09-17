import {
  Body,
  Controller,
  Delete,
  Get,
  HttpException,
  HttpStatus,
  Logger,
  Param,
  Patch,
  Post,
  Req,
  Res,
  UseGuards,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Request, Response as ExpressResponse } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';

/**
 * 会话持久化代理:前端 -> NestJS -> ai-service(FastAPI)。
 * ai-service 的会话接口要求内部服务密钥,密钥只在服务端持有,
 * 前端统一走本控制器,NestJS 负责附加 X-Service-Key 与 X-User-Id。
 */
@Controller('v1/conversations')
@UseGuards(JwtAuthGuard)
export class ConversationsController {
  private readonly logger = new Logger(ConversationsController.name);

  constructor(private readonly config: ConfigService) {}

  private baseUrl(): string {
    return (
      this.config.get<string>('AI_SERVICE_URL') ?? 'http://localhost:26010'
    ).replace(/\/+$/, '');
  }

  /** 透传请求到 ai-service 并把状态码/响应体原样返回 */
  private async forward(
    req: Request,
    res: ExpressResponse,
    method: string,
    path: string,
    body?: unknown,
  ): Promise<void> {
    const userId = (req.user as { userId: string }).userId;
    const serviceKey = this.config.get<string>('NESTJS_SERVICE_KEY');
    if (!serviceKey) {
      throw new HttpException(
        { error: { message: '服务未配置 NESTJS_SERVICE_KEY' } },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }

    let upstream: Response;
    try {
      upstream = await fetch(`${this.baseUrl()}${path}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-Service-Key': serviceKey,
          'X-User-Id': userId,
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      });
    } catch (error) {
      const reason =
        (error as { cause?: { code?: string } })?.cause?.code ??
        (error as Error).message;
      this.logger.error(`AI 服务连接失败 ${path}: ${reason}`);
      throw new HttpException(
        {
          error: {
            message: `AI 服务连接失败: ${reason}(请确认 FastAPI 服务已启动)`,
          },
        },
        HttpStatus.BAD_GATEWAY,
      );
    }

    res.status(upstream.status);
    res.setHeader(
      'Content-Type',
      upstream.headers.get('content-type') ?? 'application/json',
    );
    res.send(await upstream.text());
  }

  @Get()
  list(@Req() req: Request, @Res() res: ExpressResponse) {
    return this.forward(req, res, 'GET', '/v1/conversations');
  }

  @Post()
  create(
    @Body() body: Record<string, unknown>,
    @Req() req: Request,
    @Res() res: ExpressResponse,
  ) {
    return this.forward(req, res, 'POST', '/v1/conversations', body ?? {});
  }

  @Get(':id')
  detail(@Param('id') id: string, @Req() req: Request, @Res() res: ExpressResponse) {
    return this.forward(req, res, 'GET', `/v1/conversations/${id}`);
  }

  @Patch(':id')
  rename(
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
    @Req() req: Request,
    @Res() res: ExpressResponse,
  ) {
    return this.forward(req, res, 'PATCH', `/v1/conversations/${id}`, body ?? {});
  }

  @Delete(':id')
  remove(@Param('id') id: string, @Req() req: Request, @Res() res: ExpressResponse) {
    return this.forward(req, res, 'DELETE', `/v1/conversations/${id}`);
  }

  @Post(':id/messages')
  appendMessage(
    @Param('id') id: string,
    @Body() body: Record<string, unknown>,
    @Req() req: Request,
    @Res() res: ExpressResponse,
  ) {
    return this.forward(
      req,
      res,
      'POST',
      `/v1/conversations/${id}/messages`,
      body ?? {},
    );
  }
}
