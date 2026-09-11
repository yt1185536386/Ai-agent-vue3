package com.v3agent.gateway.ratelimit;

import com.v3agent.gateway.alert.CircuitOpenEvent;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 熔断器: 按 (策略id + 渠道id) 维度统计滑动窗口内失败率。
 * CLOSED -> (失败率超阈值) OPEN -> (冷却结束) HALF_OPEN -> (试探成功) CLOSED
 * 进入 OPEN 时发布 CircuitOpenEvent,供告警模块生成告警记录。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class CircuitBreaker {

    private final ApplicationEventPublisher eventPublisher;

    private enum State { CLOSED, OPEN, HALF_OPEN }

    private static final class Window {
        @Getter
        private State state = State.CLOSED;
        private long openUntilMillis;
        /** 窗口内 [timestampMillis, success?] */
        private final Deque<long[]> calls = new ArrayDeque<>();

        synchronized boolean allowRequest(PolicyEntity policy) {
            long now = System.currentTimeMillis();
            if (state == State.OPEN) {
                if (now < openUntilMillis) {
                    return false;
                }
                state = State.HALF_OPEN; // 放行一个试探请求
                return true;
            }
            return true;
        }

        /**
         * 记录一次调用结果并推进状态机。
         * @return 本次记录导致熔断打开时的窗口失败率;未打开返回 null
         */
        synchronized Double record(PolicyEntity policy, boolean success) {
            long now = System.currentTimeMillis();
            int windowSeconds = policy.getWindowSeconds() == null ? 60 : policy.getWindowSeconds();
            int threshold = policy.getFailureRateThreshold() == null ? 50 : policy.getFailureRateThreshold();
            int openSeconds = policy.getOpenSeconds() == null ? 60 : policy.getOpenSeconds();

            boolean openedNow = false;
            if (state == State.HALF_OPEN) {
                state = success ? State.CLOSED : State.OPEN;
                if (state == State.OPEN) {
                    openUntilMillis = now + openSeconds * 1000L;
                    openedNow = true;
                }
            }

            calls.addLast(new long[]{now, success ? 1 : 0});
            long cutoff = now - windowSeconds * 1000L;
            while (!calls.isEmpty() && calls.peekFirst()[0] < cutoff) {
                calls.pollFirst();
            }
            if (calls.isEmpty()) {
                return null;
            }
            long failures = calls.stream().filter(c -> c[1] == 0).count();
            double failureRate = failures * 100.0 / calls.size();
            if (calls.size() >= 5 && state == State.CLOSED && failureRate >= threshold) {
                state = State.OPEN;
                openUntilMillis = now + openSeconds * 1000L;
                openedNow = true;
            }
            if (openedNow) {
                log.warn("熔断打开: policy={} failureRate={}%", policy.getName(), String.format("%.1f", failureRate));
                return failureRate;
            }
            return null;
        }

        /** 供看板展示 */
        synchronized String stateName() {
            if (state == State.OPEN && System.currentTimeMillis() >= openUntilMillis) {
                return "HALF_OPEN";
            }
            return state.name();
        }
    }

    private final Map<String, Window> windows = new ConcurrentHashMap<>();

    private String key(PolicyEntity policy, String channelId) {
        return policy.getId() + ":" + (channelId == null ? "" : channelId);
    }

    /** 熔断中返回 false(供调度层跳过该渠道而不报错) */
    public boolean isOpen(PolicyEntity policy, String channelId) {
        Window w = windows.get(key(policy, channelId));
        return w != null && !w.allowRequest(policy);
    }

    public void recordSuccess(PolicyEntity policy, String channelId) {
        Double rate = windows.computeIfAbsent(key(policy, channelId), k -> new Window()).record(policy, true);
        if (rate != null) {
            eventPublisher.publishEvent(
                    new CircuitOpenEvent(this, policy.getId(), policy.getName(), channelId, rate));
        }
    }

    public void recordFailure(PolicyEntity policy, String channelId) {
        Double rate = windows.computeIfAbsent(key(policy, channelId), k -> new Window()).record(policy, false);
        if (rate != null) {
            eventPublisher.publishEvent(
                    new CircuitOpenEvent(this, policy.getId(), policy.getName(), channelId, rate));
        }
    }

    public String stateOf(PolicyEntity policy, String channelId) {
        Window w = windows.get(key(policy, channelId));
        return w == null ? "CLOSED" : w.stateName();
    }

    public void evict(String policyId) {
        windows.keySet().removeIf(k -> k.startsWith(policyId + ":"));
    }
}
