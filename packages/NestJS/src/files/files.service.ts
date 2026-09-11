import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import * as fs from 'node:fs';
import * as path from 'node:path';
import pdfParse from 'pdf-parse';
import * as mammoth from 'mammoth';

/** 直接按文本读取的扩展名 */
const TEXT_EXTS = new Set(['.txt', '.md', '.csv', '.json', '.log']);
/** 单个文档注入模型的最大字符数 */
const MAX_TEXT = 8000;
/** 上传文件保留时长:3 天 */
const FILE_TTL_MS = 3 * 24 * 60 * 60 * 1000;

export interface UploadedFileInfo {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  kind: 'image' | 'doc';
  text?: string;
}

@Injectable()
export class FilesService implements OnModuleInit {
  private readonly logger = new Logger(FilesService.name);
  private readonly uploadDir = path.join(process.cwd(), 'uploads');

  constructor() {
    fs.mkdirSync(this.uploadDir, { recursive: true });
  }

  /** 服务启动时先清理一次过期文件 */
  onModuleInit(): void {
    this.cleanExpiredUploads();
  }

  /** 每天凌晨 3 点清理超过 3 天的上传文件 */
  @Cron(CronExpression.EVERY_DAY_AT_3AM)
  cleanExpiredUploads(): void {
    const now = Date.now();
    let removed = 0;
    for (const name of fs.readdirSync(this.uploadDir)) {
      const filePath = path.join(this.uploadDir, name);
      try {
        const stat = fs.statSync(filePath);
        if (stat.isFile() && now - stat.mtimeMs > FILE_TTL_MS) {
          fs.unlinkSync(filePath);
          removed++;
        }
      } catch (error) {
        this.logger.warn(`清理文件失败 ${name}: ${error}`);
      }
    }
    if (removed > 0) {
      this.logger.log(`已清理 ${removed} 个过期上传文件`);
    }
  }

  /** 批量删除上传文件(对话删除时联动调用) */
  deleteFiles(ids: string[]): number {
    let removed = 0;
    for (const id of ids) {
      // 防目录穿越:只允许纯文件名
      if (typeof id !== 'string' || path.basename(id) !== id) continue;
      const filePath = path.join(this.uploadDir, id);
      try {
        if (fs.existsSync(filePath)) {
          fs.unlinkSync(filePath);
          removed++;
        }
      } catch (error) {
        this.logger.warn(`删除文件失败 ${id}: ${error}`);
      }
    }
    if (removed > 0) {
      this.logger.log(`已删除 ${removed} 个附件文件`);
    }
    return removed;
  }

  /** 处理上传文件:图片仅登记,文档提取文本内容返回给前端 */
  async handleUpload(file: Express.Multer.File): Promise<UploadedFileInfo> {
    const name = this.decodeName(file.originalname);
    const isImage = file.mimetype.startsWith('image/');

    const info: UploadedFileInfo = {
      id: file.filename,
      name,
      mimeType: file.mimetype,
      size: file.size,
      kind: isImage ? 'image' : 'doc',
    };

    if (!isImage) {
      info.text = await this.extractText(file, path.extname(name).toLowerCase());
    }
    return info;
  }

  /**
   * multer 1.x 用 latin1 解码文件名导致中文乱码,转回 utf8;
   * multer 2.x 已是 utf8(含非 latin1 字符),直接使用。
   */
  private decodeName(name: string): string {
    // eslint-disable-next-line no-control-regex
    return /[^\x00-\xff]/.test(name)
      ? name
      : Buffer.from(name, 'latin1').toString('utf8');
  }

  private async extractText(
    file: Express.Multer.File,
    ext: string,
  ): Promise<string> {
    try {
      if (TEXT_EXTS.has(ext)) {
        return this.truncate(fs.readFileSync(file.path, 'utf-8'));
      }
      if (ext === '.pdf') {
        const data = await pdfParse(fs.readFileSync(file.path));
        return this.truncate(data.text);
      }
      if (ext === '.docx') {
        const result = await mammoth.extractRawText({ path: file.path });
        return this.truncate(result.value);
      }
      return `(暂不支持解析 ${ext || '该类型'} 文件的内容,仅保留了文件名信息)`;
    } catch (error) {
      this.logger.error(`解析文件失败 ${file.originalname}: ${error}`);
      return '(文件内容解析失败)';
    }
  }

  private truncate(text: string): string {
    const cleaned = text.trim();
    if (!cleaned) return '(文件内容为空)';
    return cleaned.length > MAX_TEXT
      ? `${cleaned.slice(0, MAX_TEXT)}\n...(内容过长,已截断)`
      : cleaned;
  }
}
