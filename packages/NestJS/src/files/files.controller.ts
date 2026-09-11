import {
  BadRequestException,
  Body,
  Controller,
  Post,
  UploadedFiles,
  UseGuards,
  UseInterceptors,
} from '@nestjs/common';
import { FilesInterceptor } from '@nestjs/platform-express';
import { diskStorage } from 'multer';
import { randomUUID } from 'node:crypto';
import * as path from 'node:path';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { FilesService, UploadedFileInfo } from './files.service';

@Controller('v1/files')
@UseGuards(JwtAuthGuard)
export class FilesController {
  constructor(private readonly filesService: FilesService) {}

  /** 上传图片/文档,multipart 字段名 files,最多 10 个,单文件最大 20MB */
  @Post('upload')
  @UseInterceptors(
    FilesInterceptor('files', 10, {
      storage: diskStorage({
        destination: './uploads',
        filename: (_req, file, cb) => {
          cb(null, `${randomUUID()}${path.extname(file.originalname)}`);
        },
      }),
      limits: { fileSize: 20 * 1024 * 1024 },
    }),
  )
  upload(
    @UploadedFiles() files: Express.Multer.File[],
  ): Promise<UploadedFileInfo[]> {
    if (!files?.length) {
      throw new BadRequestException('未接收到文件');
    }
    return Promise.all(files.map((f) => this.filesService.handleUpload(f)));
  }

  /** 批量删除附件,body: { ids: ["uuid.ext", ...] } */
  @Post('delete')
  delete(@Body() body: { ids?: string[] }): { deleted: number } {
    if (!Array.isArray(body?.ids)) {
      throw new BadRequestException('ids 必须为数组');
    }
    return { deleted: this.filesService.deleteFiles(body.ids) };
  }
}
