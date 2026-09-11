package com.v3agent.gateway.invoke;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Lob;
import jakarta.persistence.Table;
import lombok.Data;

import java.time.LocalDateTime;

/** 调用日志: 每次模型调用的用量与结果,数据概览/调用日志页的数据源 */
@Data
@Entity
@Table(name = "invoke_logs", indexes = {
        @Index(name = "idx_logs_created", columnList = "createdAt"),
        @Index(name = "idx_logs_username", columnList = "username"),
        @Index(name = "idx_logs_model", columnList = "model")
})
public class InvokeLogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false, length = 64)
    private String userId;

    @Column(nullable = false, length = 64)
    private String username;

    @Column(nullable = false, length = 64)
    private String channelId;

    @Column(nullable = false, length = 100)
    private String channelName;

    @Column(nullable = false, length = 100)
    private String model;

    @Column(nullable = false)
    private Integer promptTokens = 0;

    @Column(nullable = false)
    private Integer completionTokens = 0;

    @Column(nullable = false)
    private Integer totalTokens = 0;

    /** 耗时毫秒 */
    @Column(nullable = false)
    private Long durationMs = 0L;

    /** 是否流式(SSE)调用 */
    @Column(nullable = false)
    private Boolean stream = false;

    /** 1 成功 / 0 失败 */
    @Column(nullable = false)
    private Integer status = 1;

    /** 全链路请求 ID(来自 X-Request-Id,经 RequestIdFilter 写入 MDC),用于跨服务日志关联 */
    @Column(length = 64)
    private String requestId;

    @Lob
    @Column(columnDefinition = "TEXT")
    private String errorMessage;

    @Column(nullable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}
