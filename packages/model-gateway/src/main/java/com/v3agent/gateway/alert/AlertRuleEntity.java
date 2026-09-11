package com.v3agent.gateway.alert;

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
 * 告警规则(独立于 policies 表): 后台异步评估,触发后写 alert_records,仅管理端看板展示。
 *
 * 指标(metric):
 *   CIRCUIT_OPEN   熔断打开(事件类,不需要 threshold/windowSeconds)
 *   RATE_LIMIT_HIT 限流命中次数(窗口内)
 *   FAILURE_RATE   失败率%(窗口内,按 invoke_logs 聚合)
 *   AVG_LATENCY_MS 平均时延毫秒(窗口内)
 *   ERROR_COUNT    错误次数(窗口内)
 *
 * 维度(targetType): GLOBAL / CHANNEL(v1 不做 USER)。
 */
@Data
@Entity
@Table(name = "alert_rules")
public class AlertRuleEntity {

    public static final String METRIC_CIRCUIT_OPEN = "CIRCUIT_OPEN";
    public static final String METRIC_RATE_LIMIT_HIT = "RATE_LIMIT_HIT";
    public static final String METRIC_FAILURE_RATE = "FAILURE_RATE";
    public static final String METRIC_AVG_LATENCY = "AVG_LATENCY_MS";
    public static final String METRIC_ERROR_COUNT = "ERROR_COUNT";

    public static final String TARGET_GLOBAL = "GLOBAL";
    public static final String TARGET_CHANNEL = "CHANNEL";

    public static final String SEVERITY_INFO = "INFO";
    public static final String SEVERITY_WARN = "WARN";
    public static final String SEVERITY_CRITICAL = "CRITICAL";

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false, length = 30)
    private String metric;

    /** GLOBAL / CHANNEL */
    @Column(nullable = false, length = 20)
    private String targetType = TARGET_GLOBAL;

    /** CHANNEL 时为渠道 id,null = 全部渠道 */
    @Column(length = 100)
    private String targetKey;

    /** 阈值(失败率=百分比 / 时延=毫秒 / 其余=次数);事件类指标不用 */
    private Double threshold;

    /** 统计窗口秒数(事件类指标不用) */
    private Integer windowSeconds;

    /** 静默期秒数: 同规则同对象触发后不重复告警 */
    private Integer cooldownSeconds = 300;

    /** INFO / WARN / CRITICAL */
    @Column(nullable = false, length = 10)
    private String severity = SEVERITY_WARN;

    /** 状态: 1 启用 / 0 停用 */
    @Column(nullable = false)
    private Integer enabled = 1;

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
