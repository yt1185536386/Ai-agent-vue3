package com.v3agent.gateway.alert;

import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 告警事件收集: 接收限流命中/熔断打开事件,缓存在内存里等评估器消费。
 * 限流命中是高频小事件,只留 10 分钟滑窗供计数;熔断打开是低频关键事件,入队等评估器逐条处理。
 */
@Component
public class AlertMetrics {

    /** 内存保留时长: 覆盖评估窗口上限即可,远超任何合理 windowSeconds */
    private static final long RETAIN_MILLIS = 10 * 60_000L;

    public record RateLimitHit(long timestampMillis, String policyId,
                               String targetType, String targetKey) {}

    public record CircuitOpen(long timestampMillis, String policyId, String policyName,
                              String channelId, double failureRate) {}

    private final Deque<RateLimitHit> rateLimitHits = new ArrayDeque<>();
    private final Deque<CircuitOpen> circuitOpenQueue = new ArrayDeque<>();

    @EventListener
    public synchronized void onRateLimitHit(RateLimitHitEvent e) {
        long now = System.currentTimeMillis();
        rateLimitHits.addLast(new RateLimitHit(now, e.getPolicyId(), e.getTargetType(), e.getTargetKey()));
        while (!rateLimitHits.isEmpty() && rateLimitHits.peekFirst().timestampMillis() < now - RETAIN_MILLIS) {
            rateLimitHits.pollFirst();
        }
    }

    @EventListener
    public synchronized void onCircuitOpen(CircuitOpenEvent e) {
        circuitOpenQueue.addLast(new CircuitOpen(System.currentTimeMillis(), e.getPolicyId(),
                e.getPolicyName(), e.getChannelId(), e.getFailureRate()));
    }

    /**
     * 统计窗口内的限流命中数,按命中对象分组。
     * @param targetType 非 null 时只统计该维度的命中(键为 targetKey);null 时合并所有维度(键为 "")
     */
    public synchronized Map<String, Integer> countRateLimitHits(long windowSeconds, String targetType) {
        long cutoff = System.currentTimeMillis() - windowSeconds * 1000L;
        Map<String, Integer> counts = new HashMap<>();
        for (RateLimitHit hit : rateLimitHits) {
            if (hit.timestampMillis() < cutoff) {
                continue;
            }
            if (targetType != null && !targetType.equals(hit.targetType())) {
                continue;
            }
            counts.merge(targetType == null ? "" : hit.targetKey(), 1, Integer::sum);
        }
        return counts;
    }

    /** 取走全部待处理熔断打开事件(评估器每个周期调用一次) */
    public synchronized List<CircuitOpen> drainCircuitOpens() {
        List<CircuitOpen> all = List.copyOf(circuitOpenQueue);
        circuitOpenQueue.clear();
        return all;
    }
}
