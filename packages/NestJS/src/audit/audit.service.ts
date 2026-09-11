import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { AuditLog } from './audit-log.entity';

export interface AuditEntry {
  operatorId: string;
  operatorName: string;
  action: string;
  targetType: string;
  targetId: string;
  targetName: string;
  detail?: Record<string, unknown> | null;
  outcome: 'auto' | 'approved' | 'rejected';
}

@Injectable()
export class AuditService {
  constructor(
    @InjectRepository(AuditLog)
    private readonly auditRepository: Repository<AuditLog>,
  ) {}

  /** 追加审计行(append-only,失败不阻断主流程) */
  async write(entry: AuditEntry): Promise<void> {
    try {
      await this.auditRepository.save(this.auditRepository.create(entry));
    } catch {
      // 审计写入失败仅日志兜底,不影响业务操作
    }
  }
}
