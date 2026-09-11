package com.v3agent.gateway.alert;

import com.v3agent.gateway.common.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * 告警规则服务: CRUD + 内存缓存(每 10s 刷新,写操作即时失效)。
 * 评估器走缓存,避免每个周期查库。模式与 PolicyService 一致。
 */
@Service
@RequiredArgsConstructor
public class AlertRuleService {

    private static final Set<String> METRICS = Set.of(
            AlertRuleEntity.METRIC_CIRCUIT_OPEN,
            AlertRuleEntity.METRIC_RATE_LIMIT_HIT,
            AlertRuleEntity.METRIC_FAILURE_RATE,
            AlertRuleEntity.METRIC_AVG_LATENCY,
            AlertRuleEntity.METRIC_ERROR_COUNT);

    private static final Set<String> SEVERITIES = Set.of(
            AlertRuleEntity.SEVERITY_INFO,
            AlertRuleEntity.SEVERITY_WARN,
            AlertRuleEntity.SEVERITY_CRITICAL);

    private final AlertRuleRepository ruleRepository;

    private final List<AlertRuleEntity> enabledCache = new CopyOnWriteArrayList<>();

    public List<AlertRuleEntity> listAll() {
        return ruleRepository.findAll();
    }

    public List<AlertRuleEntity> enabledRules() {
        return enabledCache;
    }

    @Transactional
    public AlertRuleEntity save(AlertRuleEntity rule) {
        validate(rule);
        AlertRuleEntity saved = ruleRepository.save(rule);
        refresh();
        return saved;
    }

    @Transactional
    public void delete(String id) {
        ruleRepository.deleteById(id);
        refresh();
    }

    private void validate(AlertRuleEntity r) {
        if (!METRICS.contains(r.getMetric())) {
            throw BizException.badRequest("告警指标必须是 " + METRICS + " 之一");
        }
        if (!AlertRuleEntity.TARGET_GLOBAL.equals(r.getTargetType())
                && !AlertRuleEntity.TARGET_CHANNEL.equals(r.getTargetType())) {
            throw BizException.badRequest("告警维度必须是 GLOBAL 或 CHANNEL");
        }
        if (!SEVERITIES.contains(r.getSeverity())) {
            throw BizException.badRequest("告警级别必须是 INFO / WARN / CRITICAL");
        }
        boolean eventMetric = AlertRuleEntity.METRIC_CIRCUIT_OPEN.equals(r.getMetric());
        if (!eventMetric && (r.getThreshold() == null || r.getThreshold() < 0)) {
            throw BizException.badRequest("指标类规则必须配置非负阈值");
        }
        if (!eventMetric && (r.getWindowSeconds() == null || r.getWindowSeconds() <= 0)) {
            throw BizException.badRequest("指标类规则必须配置统计窗口秒数");
        }
        if (r.getCooldownSeconds() == null || r.getCooldownSeconds() < 0) {
            throw BizException.badRequest("静默期秒数不能为负");
        }
    }

    @Scheduled(fixedDelay = 10_000, initialDelay = 1_500)
    public void refresh() {
        enabledCache.clear();
        enabledCache.addAll(ruleRepository.findByEnabled(1));
    }
}
