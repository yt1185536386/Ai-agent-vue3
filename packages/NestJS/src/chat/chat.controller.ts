import {
  BadRequestException,
  Body,
  Controller,
  Get,
  Logger,
  Post,
  Put,
  Req,
  Res,
  UseGuards,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { Readable } from 'node:stream';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { ChatService } from './chat.service';

/**
 * OpenAI 兼容代理:前端把 baseURL 指向本服务即可,
 * 支持普通 JSON 响应与 stream: true 的 SSE 流式响应。
 */
@Controller('v1')
@UseGuards(JwtAuthGuard)
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  constructor(private readonly chatService: ChatService) {}

  /** 从 JWT 载荷中取用户 id(所有用户态接口共用) */
  private uid(req: Request): string {
    return (req.user as { userId: string }).userId;
  }

  /** 查询所有模型来源及当前用户的来源 */
  @Get('providers')
  providers(@Req() req: Request) {
    return this.chatService.listProviders(this.uid(req));
  }

  /** 切换模型来源(切换后使用来源默认模型,前端需重新查询模型列表) */
  @Put('providers/current')
  async setCurrentProvider(
    @Body() body: { provider?: string },
    @Req() req: Request,
  ): Promise<{ current: string; model: string }> {
    const key = body?.provider?.trim();
    if (!key) {
      throw new BadRequestException('provider 不能为空');
    }
    const userId = this.uid(req);
    await this.chatService.setActiveProvider(userId, key);
    return {
      current: key,
      model: await this.chatService.getUserModel(userId),
    };
  }

  /** 查询当前用户来源可用的模型列表,并返回当前生效的模型及其能力 */
  @Get('models')
  async models(@Req() req: Request): Promise<{
    data: unknown;
    current: string;
    capabilities: { image: boolean; doc: boolean; thinking: boolean };
  }> {
    const userId = this.uid(req);
    const data = (await this.chatService.listModels(userId)) as {
      data?: Array<Record<string, unknown>>;
    };
    // 为每个模型附加能力标记,便于前端直接展示
    if (Array.isArray(data?.data)) {
      data.data = data.data.map((m) => ({
        ...m,
        capabilities: this.chatService.getCapabilities(
          String((m as { id?: string }).id ?? ''),
        ),
      }));
    }
    const current = await this.chatService.getUserModel(userId);
    return {
      data,
      current,
      capabilities: this.chatService.getCapabilities(current),
    };
  }

  /** 切换当前用户生效的模型 */
  @Put('models/current')
  async setCurrentModel(
    @Body() body: { model?: string },
    @Req() req: Request,
  ): Promise<{
    current: string;
    capabilities: { image: boolean; doc: boolean };
  }> {
    const model = body?.model?.trim();
    if (!model) {
      throw new BadRequestException('model 不能为空');
    }
    const userId = this.uid(req);
    await this.chatService.setActiveModel(userId, model);
    return {
      current: model,
      capabilities: this.chatService.getCapabilities(model),
    };
  }

  @Post('chat/completions')
  async completions(
    @Body() body: Record<string, any>,
    @Req() req: Request,
    @Res() res: Response,
  ): Promise<void> {
    const user = req.user as { userId: string; username: string };
    const upstream = await this.chatService.chatCompletions(
      body,
      user.userId,
      user.username,
      // 全链路请求 ID:透传给 ai-service(由其转发至 model-gateway 落计量日志)
      (req as Request & { requestId?: string }).requestId,
    );

    res.status(upstream.status);
    res.setHeader(
      'Content-Type',
      upstream.headers.get('content-type') ?? 'application/json',
    );

    if (body.stream && upstream.body) {
      // SSE 流式转发
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.flushHeaders();
      // 关键:必须给流挂 error 处理 —— 上游(ai-service)重启/断流时,
      // Readable 未捕获的 'error' 事件会打挂整个 Node 进程;
      // 这里降级为结束本次响应,客户端表现为流提前终止
      const stream = Readable.fromWeb(upstream.body as any);
      stream.on('error', (err) => {
        this.logger.warn(`SSE 上游流中断,提前结束响应: ${String(err)}`);
        if (!res.writableEnded) {
          res.end();
        }
      });
      // 客户端主动断开时取消上游流,避免悬挂的 fetch 连接
      res.on('close', () => stream.destroy());
      stream.pipe(res);
      return;
    }

    // 非流式:JSON 原样透传(AI 服务层已含 content_format/reasoning_content 等加工结果)
    res.send(await upstream.text());
  }
}
