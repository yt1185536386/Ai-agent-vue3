import { Column, Entity, PrimaryColumn } from 'typeorm';

/**
 * 模型渠道表(channels)只读映射。
 *
 * 该表由 Java model-gateway 拥有并维护(Hibernate ddl-auto),
 * 管理端(ServerManegeUI 渠道管理)经网关 /api/channels 增删改。
 * NestJS 仅在运行时只读查询启用渠道,synchronize:false 避免
 * TypeORM 与 Hibernate 两边抢 DDL。
 *
 * 注意:列名为 camelCase(网关未启用 snake_case 命名策略),
 * enableSearch 在库中是 bit(1),mysql 驱动读出为 Buffer,需转换。
 */
@Entity({ name: 'channels', synchronize: false })
export class Channel {
  @PrimaryColumn({ length: 255 })
  id: string;

  /** 渠道 key(如 company / bailian),调用方经 X-Channel-Key 指定渠道 */
  @Column({ type: 'varchar', length: 40, nullable: true })
  channelKey: string | null;

  /** 渠道名称,如 公司模型 / 百炼模型 */
  @Column({ length: 100 })
  name: string;

  /** 上游 OpenAI 兼容地址(NestJS 不直接使用,流量统一走网关) */
  @Column({ length: 500 })
  baseUrl: string;

  /** 上游 API Key(不下发,NestJS 用内部服务密钥经网关调用) */
  @Column({ length: 500 })
  apiKey: string;

  /** 支持的模型列表(JSON 数组字符串,如 ["gpt-4o","gpt-4o-mini"]) */
  @Column({ length: 4000 })
  models: string;

  /** 是否开启服务商自带联网搜索(库中 bit(1),读出为 Buffer) */
  @Column({
    transformer: {
      from: (v: unknown) =>
        v === true || v === 1 || (Buffer.isBuffer(v) && v.length > 0 && v[0] === 1),
      to: (v: boolean) => (v ? 1 : 0),
    },
  })
  enableSearch: boolean;

  /** 是否支持 tool_calls(库中 bit(1),读出为 Buffer;ai-service Agent 路径依据) */
  @Column({
    transformer: {
      from: (v: unknown) =>
        v === true || v === 1 || (Buffer.isBuffer(v) && v.length > 0 && v[0] === 1),
      to: (v: boolean) => (v ? 1 : 0),
    },
  })
  supportsTools: boolean;

  /** 调度优先级,数字越小越优先 */
  @Column()
  priority: number;

  /** 状态: 1 启用 / 0 禁用 */
  @Column()
  status: number;
}
