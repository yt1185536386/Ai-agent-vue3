package com.v3agent.gateway.alert;

import org.springframework.context.ApplicationEvent;

/** 限流命中事件: RateLimiter 在桶消费失败时发布,携带命中维度供 RATE_LIMIT_HIT 规则统计 */
public class RateLimitHitEvent extends ApplicationEvent {

    private final String policyId;
    /** 策略维度: GLOBAL / USER / CHANNEL */
    private final String targetType;
    /** 命中的桶对象(用户 名/渠道 id,全局为 "") */
    private final String targetKey;
    /** true = TPM 桶, false = QPM 桶 */
    private final boolean tokenBucket;

    public RateLimitHitEvent(Object source, String policyId, String targetType,
                             String targetKey, boolean tokenBucket) {
        super(source);
        this.policyId = policyId;
        this.targetType = targetType;
        this.targetKey = targetKey == null ? "" : targetKey;
        this.tokenBucket = tokenBucket;
    }

    public String getPolicyId() {
        return policyId;
    }

    public String getTargetType() {
        return targetType;
    }

    public String getTargetKey() {
        return targetKey;
    }

    public boolean isTokenBucket() {
        return tokenBucket;
    }
}
