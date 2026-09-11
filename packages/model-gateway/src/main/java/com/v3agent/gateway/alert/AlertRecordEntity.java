package com.v3agent.gateway.alert;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 告警触发记录(追加写流水,规则删除后保留)。
 * targetKey 归一化: 全局维度存空串 "",便于静默期查重走等值匹配。
 */
@Data
@Entity
@Table(name = "alert_records", indexes = {
        @Index(name = "idx_alert_records_status_read", columnList = "status,readFlag"),
        @Index(name = "idx_alert_records_created", columnList = "createdAt"),
        @Index(name = "idx_alert_records_rule", columnList = "ruleId")
})
public class AlertRecordEntity {

    public static final String STATUS_FIRING = "FIRING";
    public static final String STATUS_RESOLVED = "RESOLVED";

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    /** 触发规则 id(规则删除后记录保留) */
    @Column(nullable = false, length = 36)
    private String ruleId;

    /** 以下三个字段为规则快照,防规则改名/删除后历史失真 */
    @Column(nullable = false, length = 100)
    private String ruleName;

    @Column(nullable = false, length = 10)
    private String severity;

    @Column(nullable = false, length = 30)
    private String metric;

    /** 触发对象(渠道 id,全局为 "") */
    @Column(nullable = false, length = 100)
    private String targetKey = "";

    /** 触发时的实际值(失败率 72.5 / 时延 830…),事件类为 null */
    private Double metricValue;

    @Column(nullable = false, length = 500)
    private String message;

    /** FIRING / RESOLVED */
    @Column(nullable = false, length = 10)
    private String status = STATUS_FIRING;

    /** 0 未读 / 1 已读(看板红点依据) */
    @Column(nullable = false)
    private Integer readFlag = 0;

    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    private LocalDateTime resolvedAt;

    @PrePersist
    void onCreate() {
        createdAt = LocalDateTime.now();
    }
}
