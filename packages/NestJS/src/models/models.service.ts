import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Channel } from './channel.entity';

/** 供调用方(ChatService)使用的来源配置视图 */
export interface ProviderConfig {
  key: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  /** 该来源的默认模型(用户未设置时的初始值,取渠道模型列表第一个) */
  model: string;
  /** 是否开启模型服务商自带的联网搜索(如百炼 qwen 系列的 enable_search) */
  enableSearch: boolean;
}

/** 启用来源列表的缓存时长(毫秒):避免每次对话都查库,管理端变更后短延迟生效 */
const PROVIDER_CACHE_TTL = 15_000;

/**
 * 模型来源:统一以 Java model-gateway 的 channels 表为唯一数据源。
 *
 * 历史背景:此前 NestJS 自维护 model_providers 表并提供 /v1/admin/models
 * 管理接口,与管理端(ServerManegeUI -> 网关 /api/channels -> channels 表)
 * 是两套互不同步的数据,导致管理端新增渠道后客户端查不到。现已合并:
 * 渠道的增删改只在管理端进行,NestJS 这里只读启用渠道(status=1 且配置了
 * channelKey),15s 缓存短延迟生效。
 *
 * baseUrl/apiKey 不下发渠道里的上游真实地址与密钥:客户端流量统一经
 * 网关(MODEL_BASE_URL + 内部服务密钥),用 X-Channel-Key 路由到渠道,
 * 限流/熔断/计量都在网关侧完成。
 */
@Injectable()
export class ModelsService {
  private readonly logger = new Logger(ModelsService.name);
  private providerCache: { at: number; data: ProviderConfig[] } | null = null;

  constructor(
    private readonly config: ConfigService,
    @InjectRepository(Channel)
    private readonly channelRepo: Repository<Channel>,
  ) {}

  /** 启用的来源(channels 表 status=1 且配置了 channelKey,按优先级排序,带 15s 缓存) */
  async enabledProviders(): Promise<ProviderConfig[]> {
    if (
      this.providerCache &&
      Date.now() - this.providerCache.at < PROVIDER_CACHE_TTL
    ) {
      return this.providerCache.data;
    }
    const rows = await this.channelRepo
      .createQueryBuilder('c')
      .where('c.status = 1')
      .andWhere("c.channelKey IS NOT NULL AND c.channelKey != ''")
      .orderBy('c.priority', 'ASC')
      .addOrderBy('c.name', 'ASC')
      .getMany();
    // 调用入口统一为 Java model-gateway;上游真实地址/密钥留在网关侧
    const gatewayBaseUrl = (this.config.get<string>('MODEL_BASE_URL') ?? '')
      .replace(/\/+$/, '');
    const serviceKey = this.config.get<string>('MODEL_API_KEY') ?? '';
    const data = rows.map((c) => ({
      key: c.channelKey as string,
      name: c.name,
      baseUrl: gatewayBaseUrl,
      apiKey: serviceKey,
      model: parseChannelModels(c.models)[0] ?? '',
      enableSearch: c.enableSearch,
    }));
    this.providerCache = { at: Date.now(), data };
    return data;
  }
}

/** 解析渠道的模型列表 JSON(容错:非法 JSON 按空列表处理) */
function parseChannelModels(json: string): string[] {
  try {
    const parsed: unknown = JSON.parse(json);
    return Array.isArray(parsed)
      ? parsed.filter((m): m is string => typeof m === 'string' && !!m)
      : [];
  } catch {
    return [];
  }
}
