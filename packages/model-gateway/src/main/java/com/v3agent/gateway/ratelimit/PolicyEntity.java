package com.v3agent.gateway.ratelimit;

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
 * 策略配置: 限流(RATE_LIMIT)与熔断(CIRCUIT_BREAKER)共用一张策略表。
 *
 * 限流字段: qpm(每分钟请求数) / tpm(每分钟令牌数)
 * 熔断字段: failureRateThreshold(失败率阈值%) / windowSeconds(统计窗口) / openSeconds(熔断时长)
 */
@Data
@Entity
@Table(name = "policies")
public class PolicyEntity {

    public static final String TYPE_RATE_LIMIT = "RATE_LIMIT";
    public static final String TYPE_CIRCUIT_BREAKER = "CIRCUIT_BREAKER";

    public static final String TARGET_GLOBAL = "GLOBAL";
    public static final String TARGET_USER = "USER";
    public static final String TARGET_CHANNEL = "CHANNEL";

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false, length = 100)
    private String name;

    /** RATE_LIMIT / CIRCUIT_BREAKER */
    @Column(nullable = false, length = 30)
    private String type;

    /** GLOBAL / USER / CHANNEL */
    @Column(nullable = false, length = 20)
    private String targetType = TARGET_GLOBAL;

    /** targetType=USER 时为用户名,=CHANNEL 时为渠道 id,GLOBAL 时为空 */
    @Column(length = 100)
    private String targetKey;

    /** 每分钟请求数上限(null 不限制) */
    private Integer qpm;

    /** 每分钟令牌数上限(null 不限制) */
    private Integer tpm;

    /** 熔断: 失败率阈值(0-100) */
    private Integer failureRateThreshold;

    /** 熔断: 统计窗口秒数 */
    private Integer windowSeconds;

    /** 熔断: 熔断打开秒数 */
    private Integer openSeconds;

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
