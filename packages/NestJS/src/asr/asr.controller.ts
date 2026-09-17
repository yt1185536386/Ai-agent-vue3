import {
  BadRequestException,
  Controller,
  HttpException,
  HttpStatus,
  Post,
  Req,
  UploadedFile,
  UseGuards,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ConfigService } from '@nestjs/config';
import type { Request } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';

/**
 * 语音识别(ASR)转发路由:
 * 浏览器 multipart 上传 WAV → 转发 ai-service /v1/asr/transcribe → 返回 {text}。
 * 错误体保持 { error: { message } } 结构,与 chat 链路一致(前端统一解析)。
 */
@Controller('v1/asr')
@UseGuards(JwtAuthGuard)
export class AsrController {
  constructor(private readonly config: ConfigService) {}

  @Post('transcribe')
  @UseInterceptors(
    FileInterceptor('file', { limits: { fileSize: 10 * 1024 * 1024 } }),
  )
  async transcribe(
    @UploadedFile() file: Express.Multer.File,
    @Req() req: Request,
  ): Promise<{ text: string }> {
    if (!file?.buffer?.length) {
      throw new BadRequestException({
        error: { message: '未接收到音频', type: 'bad_request' },
      });
    }
    const aiServiceUrl = (
      this.config.get<string>('AI_SERVICE_URL') ?? 'http://localhost:26010'
    ).replace(/\/+$/, '');
    const serviceKey = this.config.get<string>('NESTJS_SERVICE_KEY');
    if (!serviceKey) {
      throw new HttpException(
        { error: { message: '服务未配置 NESTJS_SERVICE_KEY' } },
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }

    const fd = new FormData();
    fd.append(
      'file',
      new Blob([new Uint8Array(file.buffer)], { type: 'audio/wav' }),
      file.originalname || 'voice.wav',
    );
    let upstream: Response;
    try {
      upstream = await fetch(`${aiServiceUrl}/v1/asr/transcribe`, {
        method: 'POST',
        headers: {
          'X-Service-Key': serviceKey,
          'X-User-Id': String((req.user as { userId: string }).userId),
        },
        body: fd,
      });
    } catch (error) {
      const reason =
        (error as { cause?: { code?: string } })?.cause?.code ??
        (error as Error)?.message ??
        String(error);
      throw new HttpException(
        { error: { message: `AI 服务连接失败: ${reason}` } },
        HttpStatus.BAD_GATEWAY,
      );
    }
    const data = (await upstream.json().catch(() => ({}))) as {
      text?: string;
      error?: { message?: string };
      detail?: string;
    };
    if (!upstream.ok) {
      throw new HttpException(
        {
          error: {
            message:
              data?.error?.message ?? data?.detail ?? '语音识别失败',
          },
        },
        upstream.status,
      );
    }
    return { text: data?.text ?? '' };
  }
}
