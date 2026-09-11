package com.v3agent.gateway.ratelimit;

import com.v3agent.gateway.common.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * 策略服务: CRUD + 内存缓存(每 10s 刷新,写操作即时失效)。
 * 限流/熔断判定走缓存,避免每次调用查库。
 */
@Service
@RequiredArgsConstructor
public class PolicyService {

    private final PolicyRepository policyRepository;
    private final RateLimiter rateLimiter;
    private final CircuitBreaker circuitBreaker;

    private final List<PolicyEntity> rateLimitCache = new CopyOnWriteArrayList<>();
    private final List<PolicyEntity> circuitBreakerCache = new CopyOnWriteArrayList<>();

    public List<PolicyEntity> listAll() {
        return policyRepository.findAll();
    }

    public List<PolicyEntity> rateLimitPolicies() {
        return rateLimitCache;
    }

    public List<PolicyEntity> circuitBreakerPolicies() {
        return circuitBreakerCache;
    }

    @Transactional
    public PolicyEntity save(PolicyEntity policy) {
        validate(policy);
        PolicyEntity saved = policyRepository.save(policy);
        refresh();
        return saved;
    }

    @Transactional
    public void delete(String id) {
        policyRepository.deleteById(id);
        rateLimiter.evict(id);
        circuitBreaker.evict(id);
        refresh();
    }

    private void validate(PolicyEntity p) {
        if (!PolicyEntity.TYPE_RATE_LIMIT.equals(p.getType())
                && !PolicyEntity.TYPE_CIRCUIT_BREAKER.equals(p.getType())) {
            throw BizException.badRequest("策略类型必须是 RATE_LIMIT 或 CIRCUIT_BREAKER");
        }
        if (PolicyEntity.TYPE_RATE_LIMIT.equals(p.getType())
                && p.getQpm() == null && p.getTpm() == null) {
            throw BizException.badRequest("限流策略至少配置 QPM 或 TPM 之一");
        }
        if (PolicyEntity.TYPE_CIRCUIT_BREAKER.equals(p.getType())
                && p.getFailureRateThreshold() == null) {
            throw BizException.badRequest("熔断策略必须配置失败率阈值");
        }
    }

    @Scheduled(fixedDelay = 10_000, initialDelay = 1_000)
    public void refresh() {
        rateLimitCache.clear();
        rateLimitCache.addAll(policyRepository.findByEnabledAndType(1, PolicyEntity.TYPE_RATE_LIMIT));
        circuitBreakerCache.clear();
        circuitBreakerCache.addAll(policyRepository.findByEnabledAndType(1, PolicyEntity.TYPE_CIRCUIT_BREAKER));
    }
}
