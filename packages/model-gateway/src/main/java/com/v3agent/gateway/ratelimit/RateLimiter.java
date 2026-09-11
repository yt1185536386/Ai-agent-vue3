package com.v3agent.gateway.ratelimit;

import com.v3agent.gateway.alert.RateLimitHitEvent;
import com.v3agent.gateway.common.BizException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 令牌桶限流器: 按 (策略id + 目标key) 维度独立桶。
 * 请求数(QPM)与令牌数(TPM)分别用不同的桶前缀区分。
 * 消费失败时发布 RateLimitHitEvent,供告警模块统计限流命中。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class RateLimiter {

    private final ApplicationEventPublisher eventPublisher;

    private static final class TokenBucket {
        private final long capacityPerMinute;
        private double tokens;
        private long lastRefillNanos;

        TokenBucket(long capacityPerMinute) {
            this.capacityPerMinute = capacityPerMinute;
            this.tokens = capacityPerMinute;
            this.lastRefillNanos = System.nanoTime();
        }

        synchronized boolean tryConsume(long cost) {
            refill();
            if (tokens >= cost) {
                tokens -= cost;
                return true;
            }
            return false;
        }

        /** 结算补扣: 允许扣成负数(欠费),之后 refill 先还债,保证长期均值不超标 */
        synchronized void consumeAllowDebt(long cost) {
            refill();
            tokens -= cost;
        }

        /** 退还预扣: 加回令牌,封顶容量 */
        synchronized void refund(long amount) {
            refill();
            tokens = Math.min(capacityPerMinute, tokens + amount);
        }

        private void refill() {
            long now = System.nanoTime();
            double perNano = capacityPerMinute / 60_000_000_000.0;
            tokens = Math.min(capacityPerMinute, tokens + (now - lastRefillNanos) * perNano);
            lastRefillNanos = now;
        }
    }

    private final Map<String, TokenBucket> buckets = new ConcurrentHashMap<>();

    /** 取桶(不存在则按策略上限新建);该维度未配置上限时返回 null 表示不限制 */
    private TokenBucket bucketFor(PolicyEntity policy, String targetKey, boolean tokenBucket) {
        Integer limit = tokenBucket ? policy.getTpm() : policy.getQpm();
        if (limit == null || limit <= 0) {
            return null;
        }
        String key = policy.getId() + ":" + (tokenBucket ? "tpm:" : "qpm:") + (targetKey == null ? "" : targetKey);
        return buckets.compute(key, (k, old) ->
                (old == null || old.capacityPerMinute != limit) ? new TokenBucket(limit) : old);
    }

    /**
     * 按策略尝试消费;不抛异常仅返回 false 的版本供内部组合使用。
     * @param cost 消耗量(请求=1,令牌=实际 token 数)
     */
    public boolean tryAcquire(PolicyEntity policy, String targetKey, long cost, boolean tokenBucket) {
        TokenBucket bucket = bucketFor(policy, targetKey, tokenBucket);
        if (bucket == null) {
            return true; // 未配置该维度则不限制
        }
        boolean ok = bucket.tryConsume(cost);
        if (!ok) {
            log.debug("限流命中: policy={} target={} token={}", policy.getName(), targetKey, tokenBucket);
            eventPublisher.publishEvent(
                    new RateLimitHitEvent(this, policy.getId(), policy.getTargetType(), targetKey, tokenBucket));
        }
        return ok;
    }

    /** QPM 消费,超限抛 429 */
    public void acquireOrThrow(PolicyEntity policy, String targetKey) {
        if (!tryAcquire(policy, targetKey, 1, false)) {
            throw BizException.rateLimited("触发限流策略[" + policy.getName() + "],请求超出每分钟上限");
        }
    }

    /** TPM 预扣: 按估算成本消费,不足抛 429(请求不发往上游) */
    public void acquireTpmOrThrow(PolicyEntity policy, String targetKey, long estimatedTokens) {
        if (!tryAcquire(policy, targetKey, estimatedTokens, true)) {
            throw BizException.rateLimited("触发限流策略[" + policy.getName() + "],预估令牌超出每分钟上限");
        }
    }

    /** TPM 结算补扣: 实际用量超过预扣时追扣,允许欠费(扣成负数) */
    public void consumeTpmAllowDebt(PolicyEntity policy, String targetKey, long cost) {
        TokenBucket bucket = bucketFor(policy, targetKey, true);
        if (bucket != null) {
            bucket.consumeAllowDebt(cost);
        }
    }

    /** TPM 退还: 预扣多于实际消耗(或调用失败)时加回 */
    public void refundTpm(PolicyEntity policy, String targetKey, long amount) {
        TokenBucket bucket = bucketFor(policy, targetKey, true);
        if (bucket != null) {
            bucket.refund(amount);
        }
    }

    /** 策略删除后清理对应桶 */
    public void evict(String policyId) {
        buckets.keySet().removeIf(k -> k.startsWith(policyId + ":"));
    }
}
