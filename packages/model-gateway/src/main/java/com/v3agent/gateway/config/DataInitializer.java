package com.v3agent.gateway.config;

import com.v3agent.gateway.alert.AlertRuleEntity;
import com.v3agent.gateway.alert.AlertRuleRepository;
import com.v3agent.gateway.invoke.InvokeLogEntity;
import com.v3agent.gateway.invoke.InvokeLogRepository;
import com.v3agent.gateway.ratelimit.PolicyEntity;
import com.v3agent.gateway.ratelimit.PolicyRepository;
import com.v3agent.gateway.repo.ChannelEntity;
import com.v3agent.gateway.repo.ChannelRepository;
import com.v3agent.gateway.user.UserEntity;
import com.v3agent.gateway.user.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** 首次启动种子数据: 管理员账号 / 默认策略 / 示例渠道 / 演示调用日志 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DataInitializer implements ApplicationRunner {

    private final UserRepository userRepository;
    private final ChannelRepository channelRepository;
    private final PolicyRepository policyRepository;
    private final AlertRuleRepository alertRuleRepository;
    private final InvokeLogRepository invokeLogRepository;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Value("${gateway.seed.enabled:true}")
    private boolean seedEnabled;

    @Value("${CHANNEL_COMPANY_BASE_URL:}")
    private String companyBaseUrl;
    @Value("${CHANNEL_COMPANY_API_KEY:}")
    private String companyApiKey;
    @Value("${CHANNEL_COMPANY_MODELS:}")
    private String companyModels;
    @Value("${CHANNEL_BAILIAN_BASE_URL:}")
    private String bailianBaseUrl;
    @Value("${CHANNEL_BAILIAN_API_KEY:}")
    private String bailianApiKey;
    @Value("${CHANNEL_BAILIAN_MODELS:}")
    private String bailianModels;

    @Override
    public void run(ApplicationArguments args) {
        // 真实渠道/默认策略种子与演示种子解耦: 共用 MySQL 时(seed.enabled=false)
        // 也从环境变量写入 company/bailian 渠道与默认限流/熔断策略,让 /v1 入口开箱即可路由
        seedRealChannels();
        seedPolicies();
        seedAlertRules();
        if (!seedEnabled) {
            return;
        }
        seedUsers();
        seedChannelAndLogs();
    }

    /** 渠道表为空且配置了环境变量时,写入真实 company/bailian 渠道 */
    private void seedRealChannels() {
        if (channelRepository.count() > 0) {
            return;
        }
        if (!companyBaseUrl.isBlank()) {
            ChannelEntity c = new ChannelEntity();
            c.setName("公司模型");
            c.setChannelKey("company");
            c.setProvider("openai");
            c.setBaseUrl(companyBaseUrl.replaceAll("/+$", ""));
            c.setApiKey(companyApiKey);
            c.setModels(toJsonArray(companyModels));
            c.setPriority(1);
            c.setEnableSearch(false);
            c.setRemark("种子渠道(环境变量 CHANNEL_COMPANY_*)");
            channelRepository.save(c);
            log.info("已创建公司模型渠道: {}", c.getBaseUrl());
        }
        if (!bailianBaseUrl.isBlank()) {
            ChannelEntity c = new ChannelEntity();
            c.setName("百炼模型");
            c.setChannelKey("bailian");
            c.setProvider("qwen");
            c.setBaseUrl(bailianBaseUrl.replaceAll("/+$", ""));
            c.setApiKey(bailianApiKey);
            c.setModels(toJsonArray(bailianModels));
            c.setPriority(2);
            c.setEnableSearch(true);
            c.setRemark("种子渠道(环境变量 CHANNEL_BAILIAN_*)");
            channelRepository.save(c);
            log.info("已创建百炼模型渠道: {}", c.getBaseUrl());
        }
    }

    /** 逗号分隔的模型名 -> JSON 数组字符串 */
    private String toJsonArray(String csv) {
        List<String> models = new ArrayList<>();
        if (csv != null) {
            for (String m : csv.split(",")) {
                if (!m.isBlank()) {
                    models.add(m.trim());
                }
            }
        }
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(models);
        } catch (Exception e) {
            return "[]";
        }
    }

    private void seedUsers() {
        if (!userRepository.existsByUsername("admin")) {
            UserEntity admin = new UserEntity();
            admin.setUsername("admin");
            admin.setPasswordHash(passwordEncoder.encode("admin123"));
            admin.setDisplayName("超级管理员");
            admin.setIsSuperAdmin(true);
            userRepository.save(admin);
            log.info("已创建初始管理员: admin / admin123 / id={}", admin.getId());
        }
        if (!userRepository.existsByUsername("ysf")) {
            UserEntity demo = new UserEntity();
            demo.setUsername("ysf");
            demo.setPasswordHash(passwordEncoder.encode("123456"));
            demo.setDisplayName("演示用户");
            demo.setIsSuperAdmin(false);
            userRepository.save(demo);
        }
    }

    private void seedPolicies() {
        if (policyRepository.count() > 0) {
            return;
        }
        PolicyEntity globalQpm = new PolicyEntity();
        globalQpm.setName("全局限流(QPM)");
        globalQpm.setType(PolicyEntity.TYPE_RATE_LIMIT);
        globalQpm.setTargetType(PolicyEntity.TARGET_GLOBAL);
        globalQpm.setQpm(6000);
        globalQpm.setRemark("网关整体每分钟请求上限");
        policyRepository.save(globalQpm);

        PolicyEntity circuit = new PolicyEntity();
        circuit.setName("默认熔断策略");
        circuit.setType(PolicyEntity.TYPE_CIRCUIT_BREAKER);
        circuit.setTargetType(PolicyEntity.TARGET_GLOBAL);
        circuit.setFailureRateThreshold(50);
        circuit.setWindowSeconds(60);
        circuit.setOpenSeconds(60);
        circuit.setRemark("1 分钟窗口内失败率≥50% 熔断 60 秒");
        policyRepository.save(circuit);
        log.info("已创建默认限流/熔断策略");
    }

    /** 默认告警规则: 表为空时种子两条(熔断打开 / 全局失败率) */
    private void seedAlertRules() {
        if (alertRuleRepository.count() > 0) {
            return;
        }
        AlertRuleEntity circuitOpen = new AlertRuleEntity();
        circuitOpen.setName("渠道熔断打开");
        circuitOpen.setMetric(AlertRuleEntity.METRIC_CIRCUIT_OPEN);
        circuitOpen.setTargetType(AlertRuleEntity.TARGET_GLOBAL);
        circuitOpen.setSeverity(AlertRuleEntity.SEVERITY_CRITICAL);
        circuitOpen.setCooldownSeconds(300);
        circuitOpen.setRemark("任一渠道熔断打开即告警");
        alertRuleRepository.save(circuitOpen);

        AlertRuleEntity failureRate = new AlertRuleEntity();
        failureRate.setName("全局失败率过高");
        failureRate.setMetric(AlertRuleEntity.METRIC_FAILURE_RATE);
        failureRate.setTargetType(AlertRuleEntity.TARGET_GLOBAL);
        failureRate.setThreshold(50.0);
        failureRate.setWindowSeconds(60);
        failureRate.setCooldownSeconds(300);
        failureRate.setSeverity(AlertRuleEntity.SEVERITY_WARN);
        failureRate.setRemark("1 分钟窗口内全局失败率≥50%");
        alertRuleRepository.save(failureRate);
        log.info("已创建默认告警规则");
    }

    /** 写入一个待配置渠道 + 近 24h 演示调用日志,让数据看板开箱可见 */
    private void seedChannelAndLogs() {
        if (channelRepository.count() > 0 || invokeLogRepository.count() > 0) {
            return;
        }
        ChannelEntity channel = new ChannelEntity();
        channel.setName("公司模型");
        channel.setProvider("openai");
        channel.setBaseUrl("https://api.openai.com/v1");
        channel.setApiKey("sk-please-config-me");
        channel.setModels("[\"gpt-4o\",\"gpt-4o-mini\",\"gpt-3.5-turbo\"]");
        channel.setRemark("种子渠道:请在仓库管理中修改 baseUrl/apiKey 后启用真实调用");
        channelRepository.save(channel);

        String[] users = {"partner_globex", "dev_leo", "dev_mia", "research_yi",
                "customer_acme", "admin", "ops_root", "trial_zoe", "legacy_bot"};
        String[] models = {"gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"};
        double[] weights = {45.8, 34.2, 28.9, 19.8, 12.7, 9.8, 7.8, 5.2, 3.1};
        Random random = new Random(42);
        LocalDateTime now = LocalDateTime.now();
        List<InvokeLogEntity> logs = new ArrayList<>();
        for (int u = 0; u < users.length; u++) {
            int calls = (int) (weights[u] * 2); // 每人几十上百条,控制种子数据量
            for (int i = 0; i < calls; i++) {
                InvokeLogEntity row = new InvokeLogEntity();
                row.setUserId("seed-" + users[u]);
                row.setUsername(users[u]);
                row.setChannelId(channel.getId());
                row.setChannelName(channel.getName());
                row.setModel(models[random.nextInt(models.length)]);
                int prompt = 200 + random.nextInt(2000);
                int completion = 100 + random.nextInt(1000);
                row.setPromptTokens(prompt);
                row.setCompletionTokens(completion);
                row.setTotalTokens(prompt + completion);
                boolean ok = random.nextDouble() > 0.013; // 错误率约 1.3%
                row.setStatus(ok ? 1 : 0);
                if (!ok) {
                    row.setErrorMessage("upstream timeout");
                }
                row.setDurationMs(200L + random.nextInt(3000));
                row.setCreatedAt(now.minusMinutes(random.nextInt(24 * 60)));
                logs.add(row);
            }
        }
        invokeLogRepository.saveAll(logs);
        log.info("已写入 {} 条演示调用日志", logs.size());
    }
}
