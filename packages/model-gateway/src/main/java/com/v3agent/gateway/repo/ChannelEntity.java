package com.v3agent.gateway.repo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 模型仓库(渠道): 一个上游模型提供方接入点,
 * 对应 NestJS 网关 chat 模块中环境变量配置的 ModelProvider,改为库表管理。
 */
@Data
@Entity
@Table(name = "channels")
public class ChannelEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    /** 渠道名称,如 公司模型 / 百炼模型 */
    @Column(nullable = false, length = 100)
    private String name;

    /** 渠道 key(如 company / bailian),调用方经 X-Channel-Key 头指定渠道时按此匹配 */
    @Column(length = 40, unique = true)
    private String channelKey;

    /** 提供方类型: openai / azure / qwen / deepseek / ollama ... */
    @Column(nullable = false, length = 40)
    private String provider = "openai";

    /** 上游接口格式: openai(OpenAI 兼容)/ azure / anthropic / gemini / ollama / other;
     * 决定请求路径与认证方式的默认值,当前转发均为 OpenAI 兼容协议 */
    @Column(nullable = false, length = 40)
    private String upstreamFormat = "openai";

    /** 上游认证字段: bearer(Authorization: Bearer)/ x-api-key / api-key(Azure 头)/
     * query(URL 拼 api-key 参数)/ none(内网免认证) */
    @Column(nullable = false, length = 40)
    private String authType = "bearer";

    /** OpenAI 兼容接口地址,如 https://api.openai.com/v1 */
    @Column(nullable = false, length = 500)
    private String baseUrl;

    /** 上游 API Key */
    @Column(nullable = false, length = 500)
    private String apiKey;

    /** 支持的模型列表(JSON 数组字符串,如 ["gpt-4o","gpt-4o-mini"]) */
    @Column(nullable = false, length = 4000)
    private String models = "[]";

    /** 是否开启服务商自带联网搜索(如百炼 enable_search) */
    @Column(nullable = false)
    private Boolean enableSearch = false;

    /** 该来源是否支持 tool_calls(function calling);ai-service Agent 路径按此决定是否走工具循环 */
    @Column(nullable = false)
    private Boolean supportsTools = false;

    /** 调度优先级,数字越小越优先 */
    @Column(nullable = false)
    private Integer priority = 10;

    /** 状态: 1 启用 / 0 禁用 */
    @Column(nullable = false)
    private Integer status = 1;

    @Column(length = 500)
    private String remark;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = createdAt;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
