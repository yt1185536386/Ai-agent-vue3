import { HttpException, HttpStatus, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ModelsService, ProviderConfig } from '../models/models.service';
import { UserChatSetting } from './user-chat-setting.entity';

/** 列表中过滤掉的非对话模型(按名称匹配) */
const NON_CHAT_PATTERN = /embedding|audio|image|tts|ocr|rerank|realtime/i;

/**
 * 调用模型服务(OpenAI 兼容的 chat completions 接口)。
 * 支持多来源(公司模型 / 百炼模型等),来源统一以 Java model-gateway 的
 * channels 表为准(由 ModelsService 只读提供,管理端在渠道管理中维护),
 * 环境变量仅在查库失败时兜底。
 *
 * 每个用户的当前来源/模型持久化在 user_chat_settings 表,
 * 不再使用进程内全局状态(多用户互不影响,重启不丢失)。
 *
 * 调用计量已收敛到 Java model-gateway(invoke_logs),本服务不再记录调用日志。
 */
@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);
  /** 环境变量构造的兜底来源(数据库无启用来源时使用) */
  private readonly envProviders: ProviderConfig[];
  /** 环境变量指定的默认来源 key */
  private readonly defaultProviderKey: string;
  /** 支持图片输入的模型(名称包含匹配,* 表示全部) */
  private readonly visionModels: string[];
  /** 支持文档上传的模型 */
  private readonly docModels: string[];
  /** 支持思考模式(enable_thinking)的模型 */
  private readonly thinkingModels: string[];

  constructor(
    private readonly config: ConfigService,
    private readonly modelsService: ModelsService,
    @InjectRepository(UserChatSetting)
    private readonly settingsRepo: Repository<UserChatSetting>,
  ) {
    const strip = (s?: string) => (s ?? '').replace(/\/+$/, '');
    this.envProviders = [
      {
        key: 'company',
        name: '公司模型',
        baseUrl: strip(this.config.get<string>('MODEL_BASE_URL')),
        apiKey: this.config.get<string>('MODEL_API_KEY') ?? '',
        model: this.config.get<string>('MODEL_NAME') ?? 'gpt-4o-mini',
        enableSearch: this.config.get<string>('MODEL_ENABLE_SEARCH') === 'true',
      },
      {
        key: 'bailian',
        name: '百炼模型',
        baseUrl: strip(this.config.get<string>('BAILIAN_MODEL_BASE_URL')),
        apiKey: this.config.get<string>('BAILIAN_MODEL_API_KEY') ?? '',
        model: this.config.get<string>('BAILIAN_MODEL_NAME') ?? 'qwen-plus',
        enableSearch:
          this.config.get<string>('BAILIAN_MODEL_ENABLE_SEARCH') === 'true',
      },
      // 只保留配置了地址的来源
    ].filter((p) => p.baseUrl);

    this.defaultProviderKey =
      this.config.get<string>('MODEL_PROVIDER') ?? 'company';

    this.visionModels = this.parseList(
      this.config.get<string>('VISION_MODELS') ?? 'k3,vl',
    );
    this.docModels = this.parseList(
      this.config.get<string>('DOC_MODELS') ?? '*',
    );
    this.thinkingModels = this.parseList(
      this.config.get<string>('THINKING_MODELS') ?? 'k3,qwen3,deepseek',
    );
  }

  private parseList(value: string): string[] {
    return value
      .split(',')
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
  }

  /** 模型能力:是否支持上传图片 / 文档 / 思考模式 */
  getCapabilities(model: string): { image: boolean; doc: boolean; thinking: boolean } {
    const m = model.toLowerCase();
    const match = (list: string[]) =>
      list.includes('*') || list.some((p) => m.includes(p));
    return {
      image: match(this.visionModels),
      doc: match(this.docModels),
      thinking: match(this.thinkingModels),
    };
  }

  // ---------- 来源列表(以 channels 表为准,仅查库失败时用环境变量兜底) ----------

  /**
   * 当前可用的来源列表:channels 表中的启用渠道(status=1)。
   * 管理端禁用/删除渠道后这里立即(15s 缓存)不可见;查库本身失败
   * (如网关未建表)时才回落环境变量,保证首次部署可用。
   */
  private async getProviders(): Promise<ProviderConfig[]> {
    try {
      // 空列表也原样返回:管理端未配置/全部停用时客户端不应看到任何来源,
      // 不能再用环境变量兜底绕过管理端的禁用操作
      return await this.modelsService.enabledProviders();
    } catch (error) {
      this.logger.warn(`读取模型渠道失败,使用环境变量兜底: ${String(error)}`);
      return this.envProviders;
    }
  }

  /** 默认来源:环境变量 MODEL_PROVIDER 指定,未命中取第一个 */
  private async getDefaultProvider(
    providers: ProviderConfig[],
  ): Promise<ProviderConfig | undefined> {
    return (
      providers.find((p) => p.key === this.defaultProviderKey) ?? providers[0]
    );
  }

  // ---------- 用户态:来源与模型(user_chat_settings 表) ----------

  /** 读取用户偏好;不存在时按默认来源创建(一人一行的稀疏表) */
  private async resolveSettings(userId: string): Promise<UserChatSetting> {
    let row = await this.settingsRepo.findOne({ where: { userId } });
    if (!row) {
      const providers = await this.getProviders();
      const defaultProvider = await this.getDefaultProvider(providers);
      row = this.settingsRepo.create({
        userId,
        provider: defaultProvider?.key ?? '',
        model: defaultProvider?.model ?? '',
      });
      try {
        row = await this.settingsRepo.save(row);
      } catch {
        // 并发首次访问撞唯一键时,回读已创建的行
        row = (await this.settingsRepo.findOne({ where: { userId } })) ?? row;
      }
    }
    return row;
  }

  /** 用户当前生效的来源(存了非法/已停用 key 时回落到默认来源) */
  private async getUserProvider(
    userId: string,
  ): Promise<ProviderConfig | undefined> {
    const providers = await this.getProviders();
    const settings = await this.resolveSettings(userId);
    return (
      providers.find((p) => p.key === settings.provider) ??
      (await this.getDefaultProvider(providers))
    );
  }

  /** 用户当前生效的模型 */
  async getUserModel(userId: string): Promise<string> {
    const settings = await this.resolveSettings(userId);
    return settings.model || (await this.getUserProvider(userId))?.model || '';
  }

  /** 所有可用的模型来源及当前用户的来源 */
  async listProviders(
    userId: string,
  ): Promise<{ providers: { key: string; name: string }[]; current: string }> {
    const providers = await this.getProviders();
    const provider = await this.getUserProvider(userId);
    return {
      providers: providers.map(({ key, name }) => ({ key, name })),
      current: provider?.key ?? '',
    };
  }

  /** 切换模型来源,同时切换到该来源的默认模型 */
  async setActiveProvider(userId: string, key: string): Promise<void> {
    const providers = await this.getProviders();
    const provider = providers.find((p) => p.key === key);
    if (!provider) {
      throw new HttpException(
        `未知的模型来源: ${key}`,
        HttpStatus.BAD_REQUEST,
      );
    }
    const settings = await this.resolveSettings(userId);
    settings.provider = provider.key;
    settings.model = provider.model;
    await this.settingsRepo.save(settings);
    this.logger.log(
      `用户 ${userId} 模型来源已切换为: ${provider.name}(${provider.key})`,
    );
  }

  /** 切换当前用户生效的模型 */
  async setActiveModel(userId: string, model: string): Promise<void> {
    const settings = await this.resolveSettings(userId);
    settings.model = model;
    await this.settingsRepo.save(settings);
    this.logger.log(`用户 ${userId} 模型已切换为: ${model}`);
  }

  /** 查询当前用户来源可用的对话模型列表 */
  async listModels(userId: string): Promise<unknown> {
    const provider = await this.getUserProvider(userId);
    if (!provider) {
      this.throwOpenAIError(
        '未配置任何可用的模型来源,请联系管理员',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
    let upstream: Response;
    try {
      // 模型出口统一走 Java model-gateway 时:/models 经 X-Service-Key 内部鉴权、
      // X-Channel-Key 指定渠道透传上游;对非网关来源这两个头无害(被忽略)
      const serviceKey = this.config.get<string>('NESTJS_SERVICE_KEY');
      upstream = await fetch(`${provider.baseUrl}/models`, {
        headers: {
          ...(provider.apiKey
            ? { Authorization: `Bearer ${provider.apiKey}` }
            : {}),
          ...(serviceKey ? { 'X-Service-Key': serviceKey } : {}),
          'X-Channel-Key': provider.key,
        },
      });
    } catch (error) {
      const reason = this.describeNetworkError(error);
      this.logger.error(
        `模型服务连接失败 [${provider.name}] ${provider.baseUrl}/models: ${reason}`,
      );
      this.throwOpenAIError(
        `模型服务连接失败 [${provider.name}]: ${reason}(${provider.baseUrl}/models)`,
        HttpStatus.BAD_GATEWAY,
      );
    }

    if (!upstream.ok) {
      const detail = await upstream.text();
      this.logger.error(`查询模型列表失败 ${upstream.status}: ${detail}`);
      this.throwOpenAIError(
        `查询模型列表失败 [${provider.name}] HTTP ${upstream.status}: ${detail}`,
        HttpStatus.BAD_GATEWAY,
      );
    }

    const data = (await upstream.json()) as {
      data?: Array<Record<string, unknown>>;
    };
    // 过滤掉 embedding / 语音 / 图像生成等非对话模型
    if (Array.isArray(data?.data)) {
      data.data = data.data.filter(
        (m) => !NON_CHAT_PATTERN.test(String((m as { id?: string }).id ?? '')),
      );
    }
    return data;
  }


  /**
   * 从 fetch 抛出的网络层错误中提取可读原因。
   * Node fetch 会把底层错误放在 cause 上(如 ECONNREFUSED / ETIMEDOUT / ENOTFOUND)。
   */
  private describeNetworkError(error: unknown): string {
    const err = error as { message?: string; cause?: { code?: string; message?: string } };
    const cause = err?.cause;
    if (cause?.code) {
      return `${cause.code}${cause.message ? `(${cause.message})` : ''}`;
    }
    return err?.message || String(error);
  }

  /**
   * 构造 OpenAI 兼容的错误响应体并抛出。
   * 注意:必须是 { error: { message } } 结构 —— OpenAI SDK(前端 LangChain 依赖)
   * 解析错误时只读 body 的 error 字段,NestJS 默认的 { statusCode, message }
   * 结构会被 SDK 丢弃,前端只能看到 "403 status code (no body)"。
   */
  private throwOpenAIError(message: string, status: number): never {
    throw new HttpException(
      {
        error: {
          message,
          type: 'upstream_error',
          param: null,
          code: null,
        },
      },
      status,
    );
  }


  /**
   * 转发 chat completions 请求到 AI 服务层(FastAPI),由 AI 服务层
   * 再经 Java model-gateway 转发到对应的模型来源。返回原始 fetch Response
   * (由调用方决定按 JSON 还是 SSE 流处理)。
   * 失败时抛出带详细原因的 HttpException,前端可直接展示。
   *
   * 步骤 4 起,NestJS 仅保留路由职责:强制模型、附带来源信息,
   * 时间注入/联网搜索/思考模式剔除等加工统一在 AI 服务层完成,
   * 限流/熔断/计量统一在 Java model-gateway 完成。
   */
  async chatCompletions(
    body: Record<string, unknown>,
    userId: string,
    username = '',
    requestId = '',
  ): Promise<Response> {
    const provider = await this.getUserProvider(userId);
    if (!provider) {
      this.throwOpenAIError(
        '未配置任何可用的模型来源,请联系管理员',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
    const userModel = await this.getUserModel(userId);
    const stream = body.stream === true;
    const aiServiceUrl = (
      this.config.get<string>('AI_SERVICE_URL') ?? 'http://localhost:6010'
    ).replace(/\/+$/, '');
    const target = `${aiServiceUrl}/v1/chat/completions`;

    const serviceKey = this.config.get<string>('NESTJS_SERVICE_KEY');
    if (!serviceKey) {
      this.throwOpenAIError(
        '服务未配置 NESTJS_SERVICE_KEY，无法安全调用 AI 服务',
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }

    let upstream: Response;
    const requestBody = { ...body, model: userModel };
    const forwardHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Provider': provider.key,
      'X-Service-Key': serviceKey,
      'X-User-Id': userId,
      // 用户名经 URL 编码透传(中文无法直接放 HTTP 头),
      // ai-service 会原样转发给 Java 模型网关作用户维度计量
      'X-Username': encodeURIComponent(username),
      // 全链路请求 ID:model-gateway 落 invoke_logs,排障时一个 id 贯穿三层
      ...(requestId ? { 'X-Request-Id': requestId } : {}),
    };

    try {
      upstream = await fetch(target, {
        method: 'POST',
        headers: forwardHeaders,
        body: JSON.stringify(requestBody),
      });
    } catch (error) {
      // 网络层失败:AI 服务层未启动 / 端口不通 / DNS 解析失败等
      const reason = this.describeNetworkError(error);
      this.logger.error(`AI 服务连接失败 ${target}: ${reason}`);
      this.throwOpenAIError(
        `AI 服务连接失败: ${reason}(${target},请确认 FastAPI 服务已启动)`,
        HttpStatus.BAD_GATEWAY,
      );
    }

    if (!upstream.ok) {
      let detail: string;
      try {
        detail = await upstream.text();
      } catch {
        detail = '(读取错误响应体失败)';
      }
      this.logger.error(
        `AI 服务调用失败 [${provider.name}/${userModel}] ${upstream.status}: ${detail}`,
      );
      this.throwOpenAIError(
        `AI 服务调用失败 [${provider.name}/${userModel}] HTTP ${upstream.status}: ${detail}`,
        upstream.status >= 400 && upstream.status < 600
          ? upstream.status
          : HttpStatus.BAD_GATEWAY,
      );
    }

    if (stream) {
      // SSE 流式:响应头已拿到即视为调用成功,直接透传不拦截
      return upstream;
    }

    // 非流式:读全响应后原样返回(token 计量在 Java model-gateway 完成)
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: {
        'content-type':
          upstream.headers.get('content-type') ?? 'application/json',
      },
    });
  }
}
