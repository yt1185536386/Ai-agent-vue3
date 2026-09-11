import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Channel } from './channel.entity';
import { ModelsService } from './models.service';

/**
 * 模型来源模块:只读 channels 表(网关侧唯一数据源)。
 * 管理端增删改统一走 ServerManegeUI -> Java model-gateway /api/channels,
 * 原 /v1/admin/models 接口与 model_providers 表已废弃。
 */
@Module({
  imports: [TypeOrmModule.forFeature([Channel])],
  providers: [ModelsService],
  exports: [ModelsService],
})
export class ModelsModule {}
