package com.v3agent.gateway.alert;

import com.v3agent.gateway.invoke.InvokeLogRepository;
import com.v3agent.gateway.ratelimit.CircuitBreaker;
import com.v3agent.gateway.ratelimit.PolicyEntity;
import com.v3agent.gateway.ratelimit.PolicyService;
import com.v3agent.gateway.repo.ChannelRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 告警评估引擎: 每 15s 一轮。
 * ① 处理熔断打开事件队列(CIRCUIT_OPEN);
 * ② 聚合 invoke_logs 评估 FAILURE_RATE / AVG_LATENCY_MS / ERROR_COUNT;
 * ③ 统计内存滑窗评估 RATE_LIMIT_HIT;
 * ④ 超阈值且不在静默期 -> 插 FIRING 记录;回落到阈值下 -> 活跃记录置 RESOLVED;
 * ⑤ 每小时清理 30 天前的历史记录。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AlertEvaluator {

    /** 历史记录保留天数 */
    private static final int RETENTION_DAYS = 30;

    private final AlertRuleService ruleService;
    private final AlertRecordRepository recordRepository;
    private final AlertMetrics metrics;
    private final InvokeLogRepository logRepository;
    private final PolicyService policyService;
    private final CircuitBreaker circuitBreaker;
    private final ChannelRepository channelRepository;

    private volatile long lastCleanupMillis;

    @Transactional
    @Scheduled(fixedDelay = 15_000, initialDelay = 5_000)
    public void evaluate() {
        List<AlertRuleEntity> rules = ruleService.enabledRules();
        if (!rules.isEmpty()) {
            handleCircuitOpenEvents(rules);
            evaluateMetricRules(rules);
            resolveClosedCircuits(rules);
        }
        cleanupIfDue();
    }

    // ---------- 熔断打开(事件类) ----------

    private void handleCircuitOpenEvents(List<AlertRuleEntity> rules) {
        List<AlertMetrics.CircuitOpen> opens = metrics.drainCircuitOpens();
        if (opens.isEmpty()) {
            return;
        }
        List<AlertRuleEntity> circuitRules = rules.stream()
                .filter(r -> AlertRuleEntity.METRIC_CIRCUIT_OPEN.equals(r.getMetric()))
                .toList();
        for (AlertMetrics.CircuitOpen open : opens) {
            for (AlertRuleEntity rule : circuitRules) {
                if (!matchesChannel(rule, open.channelId())) {
                    continue;
                }
                String message = "渠道[" + channelName(open.channelId()) + "]熔断打开,窗口失败率 "
                        + String.format("%.1f", open.failureRate()) + "%";
                fire(rule, open.channelId(), open.failureRate(), message);
            }
        }
    }

    /** 渠道熔断全部闭合后,把 CIRCUIT_OPEN 的活跃记录置 RESOLVED */
    private void resolveClosedCircuits(List<AlertRuleEntity> rules) {
        boolean hasCircuitRule = rules.stream()
                .anyMatch(r -> AlertRuleEntity.METRIC_CIRCUIT_OPEN.equals(r.getMetric()));
        if (!hasCircuitRule) {
            return;
        }
        List<AlertRecordEntity> firing = recordRepository.findByStatusAndMetric(
                AlertRecordEntity.STATUS_FIRING, AlertRuleEntity.METRIC_CIRCUIT_OPEN);
        for (AlertRecordEntity rec : firing) {
            if (!isAnyCircuitOpen(rec.getTargetKey())) {
                resolve(rec);
            }
        }
    }

    private boolean isAnyCircuitOpen(String channelId) {
        for (PolicyEntity policy : policyService.circuitBreakerPolicies()) {
            if (circuitBreaker.isOpen(policy, channelId)) {
                return true;
            }
        }
        return false;
    }

    // ---------- 指标类规则 ----------

    private void evaluateMetricRules(List<AlertRuleEntity> rules) {
        LocalDateTime now = LocalDateTime.now();
        for (AlertRuleEntity rule : rules) {
            switch (rule.getMetric()) {
                case AlertRuleEntity.METRIC_CIRCUIT_OPEN -> { /* 事件类已处理 */ }
                case AlertRuleEntity.METRIC_RATE_LIMIT_HIT -> evaluateRateLimitHit(rule);
                default -> evaluateLogMetric(rule, now);
            }
        }
    }

    /** RATE_LIMIT_HIT: 内存滑窗计数,按规则维度过滤 */
    private void evaluateRateLimitHit(AlertRuleEntity rule) {
        boolean channelScoped = AlertRuleEntity.TARGET_CHANNEL.equals(rule.getTargetType());
        Map<String, Integer> counts = metrics.countRateLimitHits(
                rule.getWindowSeconds(), channelScoped ? AlertRuleEntity.TARGET_CHANNEL : null);
        if (channelScoped && rule.getTargetKey() != null) {
            Integer count = counts.get(rule.getTargetKey());
            counts = count == null ? Map.of() : Map.of(rule.getTargetKey(), count);
        }
        if (!channelScoped) {
            // GLOBAL: 全部维度命中合并为一个 "" 键
            int total = counts.values().stream().mapToInt(Integer::intValue).sum();
            counts = Map.of("", total);
        }
        for (Map.Entry<String, Integer> e : counts.entrySet()) {
            checkAndFire(rule, e.getKey(), e.getValue(),
                    e.getValue() + " 次", channelScoped && !e.getKey().isEmpty()
                            ? channelName(e.getKey()) : "全局");
        }
        // CHANNEL 指定渠道但窗口内无命中时,也要给回落检测一次机会
        if (counts.isEmpty() && channelScoped && rule.getTargetKey() != null) {
            checkAndFire(rule, rule.getTargetKey(), 0, "0 次", channelName(rule.getTargetKey()));
        }
    }

    /** FAILURE_RATE / AVG_LATENCY_MS / ERROR_COUNT: 聚合 invoke_logs 按渠道评估 */
    private void evaluateLogMetric(AlertRuleEntity rule, LocalDateTime now) {
        LocalDateTime start = now.minusSeconds(rule.getWindowSeconds());
        List<InvokeLogRepository.ChannelWindowStat> stats = logRepository.windowStatByChannel(start, now);

        boolean channelScoped = AlertRuleEntity.TARGET_CHANNEL.equals(rule.getTargetType());
        if (rule.getTargetKey() != null) {
            stats = stats.stream().filter(s -> rule.getTargetKey().equals(s.getChannelId())).toList();
        }
        if (!channelScoped) {
            // GLOBAL: 全渠道合并成一行
            long calls = stats.stream().mapToLong(InvokeLogRepository.ChannelWindowStat::getCalls).sum();
            long errors = stats.stream().mapToLong(InvokeLogRepository.ChannelWindowStat::getErrors).sum();
            double latencySum = stats.stream()
                    .mapToDouble(s -> (s.getAvgDuration() == null ? 0 : s.getAvgDuration()) * s.getCalls()).sum();
            evaluateOneTarget(rule, "", "全局", calls, errors, calls == 0 ? 0 : latencySum / calls);
            return;
        }
        for (InvokeLogRepository.ChannelWindowStat s : stats) {
            evaluateOneTarget(rule, s.getChannelId(), s.getChannelName(),
                    s.getCalls(), s.getErrors(), s.getAvgDuration() == null ? 0 : s.getAvgDuration());
        }
    }

    private void evaluateOneTarget(AlertRuleEntity rule, String targetKey, String targetLabel,
                                   long calls, long errors, double avgDuration) {
        double value;
        String valueText;
        String thresholdText;
        switch (rule.getMetric()) {
            case AlertRuleEntity.METRIC_FAILURE_RATE -> {
                value = calls == 0 ? 0 : errors * 100.0 / calls;
                valueText = String.format("%.1f%%", value);
                thresholdText = String.format("%.0f%%", rule.getThreshold());
            }
            case AlertRuleEntity.METRIC_AVG_LATENCY -> {
                value = avgDuration;
                valueText = String.format("%.0fms", value);
                thresholdText = String.format("%.0fms", rule.getThreshold());
            }
            default -> { // ERROR_COUNT
                value = errors;
                valueText = errors + " 次";
                thresholdText = String.format("%.0f", rule.getThreshold()) + " 次";
            }
        }
        checkAndFire(rule, targetKey, value, valueText, thresholdText, targetLabel);
    }

    // ---------- 触发 / 恢复 ----------

    /** RATE_LIMIT_HIT 走这个简化重载 */
    private void checkAndFire(AlertRuleEntity rule, String targetKey, double value,
                              String valueText, String targetLabel) {
        checkAndFire(rule, targetKey, value, valueText,
                String.format("%.0f", rule.getThreshold()) + " 次", targetLabel);
    }

    /** 超阈值且不在静默期 -> 触发;低于阈值 -> 活跃记录置 RESOLVED */
    private void checkAndFire(AlertRuleEntity rule, String targetKey, double value,
                              String valueText, String thresholdText, String targetLabel) {
        String key = targetKey == null ? "" : targetKey;
        if (value >= rule.getThreshold()) {
            String message = targetLabel + " " + rule.getWindowSeconds() + "s 内"
                    + metricLabel(rule.getMetric()) + " " + valueText + " ≥ 阈值 " + thresholdText;
            fire(rule, key, value, message);
        } else {
            recordRepository.findByStatusAndRuleIdAndTargetKey(
                    AlertRecordEntity.STATUS_FIRING, rule.getId(), key).forEach(this::resolve);
        }
    }

    /** 静默期查重后插入 FIRING 记录 */
    private void fire(AlertRuleEntity rule, String targetKey, Double metricValue, String message) {
        String key = targetKey == null ? "" : targetKey;
        LocalDateTime cooldownAfter = LocalDateTime.now().minusSeconds(rule.getCooldownSeconds());
        if (recordRepository.existsByRuleIdAndTargetKeyAndCreatedAtAfter(rule.getId(), key, cooldownAfter)) {
            return;
        }
        AlertRecordEntity rec = new AlertRecordEntity();
        rec.setRuleId(rule.getId());
        rec.setRuleName(rule.getName());
        rec.setSeverity(rule.getSeverity());
        rec.setMetric(rule.getMetric());
        rec.setTargetKey(key);
        rec.setMetricValue(metricValue);
        rec.setMessage(message);
        recordRepository.save(rec);
        log.warn("告警触发[{}]: {}", rule.getSeverity(), message);
    }

    private void resolve(AlertRecordEntity rec) {
        rec.setStatus(AlertRecordEntity.STATUS_RESOLVED);
        rec.setResolvedAt(LocalDateTime.now());
        recordRepository.save(rec);
        log.info("告警恢复: {}", rec.getMessage());
    }

    // ---------- 工具 ----------

    private boolean matchesChannel(AlertRuleEntity rule, String channelId) {
        return AlertRuleEntity.TARGET_GLOBAL.equals(rule.getTargetType())
                || rule.getTargetKey() == null
                || rule.getTargetKey().equals(channelId);
    }

    private String channelName(String channelId) {
        return channelRepository.findById(channelId)
                .map(c -> c.getName()).orElse(channelId);
    }

    private String metricLabel(String metric) {
        return switch (metric) {
            case AlertRuleEntity.METRIC_RATE_LIMIT_HIT -> "限流命中";
            case AlertRuleEntity.METRIC_FAILURE_RATE -> "失败率";
            case AlertRuleEntity.METRIC_AVG_LATENCY -> "平均时延";
            case AlertRuleEntity.METRIC_ERROR_COUNT -> "错误数";
            default -> metric;
        };
    }

    private void cleanupIfDue() {
        long now = System.currentTimeMillis();
        if (now - lastCleanupMillis < 3_600_000L) {
            return;
        }
        lastCleanupMillis = now;
        int deleted = recordRepository.deleteOlderThan(LocalDateTime.now().minusDays(RETENTION_DAYS));
        if (deleted > 0) {
            log.info("已清理 {} 条 {} 天前的告警记录", deleted, RETENTION_DAYS);
        }
    }
}
