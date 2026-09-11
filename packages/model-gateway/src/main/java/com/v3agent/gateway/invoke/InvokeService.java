package com.v3agent.gateway.invoke;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.v3agent.gateway.auth.CurrentUser;
import com.v3agent.gateway.common.BizException;
import com.v3agent.gateway.ratelimit.CircuitBreaker;
import com.v3agent.gateway.ratelimit.PolicyEntity;
import com.v3agent.gateway.ratelimit.PolicyService;
import com.v3agent.gateway.ratelimit.RateLimiter;
import com.v3agent.gateway.repo.ChannelAuth;
import com.v3agent.gateway.repo.ChannelEntity;
import com.v3agent.gateway.repo.ChannelService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 模型调用核心(唯一模型出口): 限流(QPM) + TPM 预扣 -> 渠道调度(跳过熔断)
 * -> 上游转发 -> 熔断统计 + TPM 结算(多退少补) + 用量落库。
 * TPM 用主流两段式: 转发前按 prompt 粗估 + max_tokens 预扣,不足直接 429 不调上游;
 * 响应回来后按真实 usage 结算,实际少于预估退差额,多于预估补扣(允许欠费)。
 * 入方向只认内部服务密钥(ServiceKeyInterceptor),用户身份经 X-User-Id 透传作限流/计量维度。
 * 渠道选择: 调用方带 X-Channel-Key 头时按渠道 key 精确路由,否则按模型列表匹配。
 */
@Slf4j
@Service
public class InvokeService {

    private final ChannelService channelService;
    private final PolicyService policyService;
    private final RateLimiter rateLimiter;
    private final CircuitBreaker circuitBreaker;
    private final InvokeLogRepository logRepository;
    private final RestClient restClient;
    private final HttpClient streamHttpClient;
    private final ObjectMapper mapper = new ObjectMapper();

    public InvokeService(ChannelService channelService,
                         PolicyService policyService,
                         RateLimiter rateLimiter,
                         CircuitBreaker circuitBreaker,
                         InvokeLogRepository logRepository,
                         @Value("${gateway.invoke.connect-timeout-ms}") int connectTimeoutMs,
                         @Value("${gateway.invoke.read-timeout-ms}") int readTimeoutMs) {
        this.channelService = channelService;
        this.policyService = policyService;
        this.rateLimiter = rateLimiter;
        this.circuitBreaker = circuitBreaker;
        this.logRepository = logRepository;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(connectTimeoutMs));
        factory.setReadTimeout(Duration.ofMillis(readTimeoutMs));
        this.restClient = RestClient.builder().requestFactory(factory).build();
        // 流式转发单独一个 client: 只设连接超时,长 SSE 流不受读超时限制
        this.streamHttpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(connectTimeoutMs))
                .build();
    }

    // ---------- 非流式 chat completions ----------

    /**
     * 转发一次非流式 chat completions 调用。
     * @param user       调用方透传的用户(限流/计量维度)
     * @param payload    OpenAI 兼容请求体(必须含 model)
     * @param channelKey 调用方指定的渠道 key(X-Channel-Key),可为 null
     * @return 上游响应 JSON
     */
    public JsonNode chatCompletions(CurrentUser user, ObjectNode payload, String channelKey) {
        String model = requireModel(payload);
        ChannelEntity channel = selectChannel(user, model, channelKey);
        TpmReservation tpm = reserveTpm(channel, user, estimateRequestTokens(payload));

        long start = System.currentTimeMillis();
        InvokeLogEntity logRow = newLogRow(user, channel, model);

        try {
            ObjectNode body = payload.deepCopy();
            if (Boolean.TRUE.equals(channel.getEnableSearch()) && !body.has("enable_search")) {
                body.put("enable_search", true);
            }
            JsonNode resp = ChannelAuth.apply(restClient.post()
                    .uri(ChannelAuth.authUri(channel.getBaseUrl() + "/chat/completions", channel))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body), channel)
                    .retrieve()
                    .body(JsonNode.class);

            int promptTokens = resp == null ? 0 : resp.path("usage").path("prompt_tokens").asInt(0);
            int completionTokens = resp == null ? 0 : resp.path("usage").path("completion_tokens").asInt(0);
            if (promptTokens == 0 && completionTokens == 0) {
                // 上游未返回 usage 时按字符数粗估,保证看板有数据
                promptTokens = estimateTokens(body.path("messages").toString());
                completionTokens = estimateTokens(resp == null ? "" : resp.path("choices").toString());
            }
            logRow.setPromptTokens(promptTokens);
            logRow.setCompletionTokens(completionTokens);
            logRow.setTotalTokens(promptTokens + completionTokens);
            logRow.setStatus(1);
            recordCircuit(channel, true);
            tpm.settle(rateLimiter, logRow.getTotalTokens());
            return resp;
        } catch (Exception e) {
            tpm.release(rateLimiter);
            logRow.setStatus(0);
            logRow.setErrorMessage(truncate(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
            recordCircuit(channel, false);
            throw BizException.badRequest("模型调用失败: " + e.getMessage());
        } finally {
            saveLog(logRow, start);
        }
    }

    // ---------- 流式(SSE)chat completions ----------

    /**
     * 流式转发: 直接写 HttpServletResponse(上游响应头到达后逐 chunk 透传,
     * 同时累积尾部文本,流末从 usage 块提取 token 用量,没有则粗估落库)。
     * 上游非 2xx 时在响应未提交前抛出,调用方拿到 OpenAI 兼容错误体。
     */
    public void chatCompletionsStream(CurrentUser user, ObjectNode payload, String channelKey,
                                      jakarta.servlet.http.HttpServletResponse response) throws IOException {
        String model = requireModel(payload);
        ChannelEntity channel = selectChannel(user, model, channelKey);
        TpmReservation tpm = reserveTpm(channel, user, estimateRequestTokens(payload));

        long start = System.currentTimeMillis();
        InvokeLogEntity logRow = newLogRow(user, channel, model);
        logRow.setStream(true);

        ObjectNode body = payload.deepCopy();
        if (Boolean.TRUE.equals(channel.getEnableSearch()) && !body.has("enable_search")) {
            body.put("enable_search", true);
        }
        HttpRequest request = ChannelAuth.apply(HttpRequest.newBuilder()
                .uri(URI.create(ChannelAuth.authUri(channel.getBaseUrl() + "/chat/completions", channel))), channel)
                .header("Content-Type", "application/json")
                .header("Accept", "text/event-stream")
                .POST(HttpRequest.BodyPublishers.ofString(body.toString(), StandardCharsets.UTF_8))
                .build();

        final HttpResponse<InputStream> upstream;
        try {
            upstream = streamHttpClient.send(request, HttpResponse.BodyHandlers.ofInputStream());
        } catch (Exception e) {
            tpm.release(rateLimiter);
            logRow.setStatus(0);
            logRow.setErrorMessage(truncate("上游连接失败: " + e.getMessage()));
            recordCircuit(channel, false);
            saveLog(logRow, start);
            throw BizException.badRequest("模型调用失败: 上游连接失败: " + e.getMessage());
        }
        if (upstream.statusCode() != 200) {
            String errBody;
            try {
                errBody = new String(upstream.body().readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException e) {
                errBody = "(读取上游错误体失败)";
            }
            tpm.release(rateLimiter);
            logRow.setStatus(0);
            logRow.setErrorMessage(truncate("HTTP " + upstream.statusCode() + ": " + errBody));
            recordCircuit(channel, false);
            saveLog(logRow, start);
            throw BizException.badRequest("模型调用失败 HTTP " + upstream.statusCode() + ": " + truncate(errBody));
        }

        response.setStatus(200);
        response.setContentType(MediaType.TEXT_EVENT_STREAM_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader("Cache-Control", "no-cache");
        response.setHeader("X-Accel-Buffering", "no");
        response.flushBuffer();
        teeStream(upstream.body(), response.getOutputStream(), body, logRow, channel, user, tpm, start);
    }

    /** 把上游 SSE 字节流原样透传给客户端,同时累积尾部文本供流末计量与 TPM 结算 */
    private void teeStream(InputStream in, OutputStream out, ObjectNode requestBody,
                           InvokeLogEntity logRow, ChannelEntity channel, CurrentUser user,
                           TpmReservation tpm, long start) throws IOException {
        // 尾部缓冲: usage 块在流末尾,64KB 足够容纳
        StringBuilder tail = new StringBuilder();
        boolean clientAlive = true;
        boolean upstreamOk = true;
        byte[] buf = new byte[8192];
        try (in) {
            int n;
            while ((n = in.read(buf)) != -1) {
                appendCapped(tail, new String(buf, 0, n, StandardCharsets.UTF_8), 64 * 1024);
                if (clientAlive) {
                    try {
                        out.write(buf, 0, n);
                        out.flush();
                    } catch (IOException e) {
                        // 客户端断开: 继续耗尽上游流以便拿到 usage 计量,不再写
                        clientAlive = false;
                    }
                }
            }
        } catch (IOException e) {
            // 流中断拿不到 usage,无法结算,退还全部预扣
            tpm.release(rateLimiter);
            upstreamOk = false;
            logRow.setStatus(0);
            logRow.setErrorMessage(truncate("流式读取中断: " + e.getMessage()));
            recordCircuit(channel, false);
            saveLog(logRow, start);
            throw e;
        }
        // 流正常结束: 从尾部文本提取 usage,没有则粗估
        int[] usage = parseStreamUsage(tail);
        int promptTokens = usage[0] > 0 ? usage[0] : estimateTokens(requestBody.path("messages").toString());
        int completionTokens = usage[1] > 0 ? usage[1] : estimateTokens(stripSseEnvelope(tail.toString()));
        logRow.setPromptTokens(promptTokens);
        logRow.setCompletionTokens(completionTokens);
        logRow.setTotalTokens(promptTokens + completionTokens);
        logRow.setStatus(clientAlive ? 1 : 0);
        if (!clientAlive) {
            logRow.setErrorMessage("客户端中途断开");
        }
        if (upstreamOk) {
            recordCircuit(channel, true);
        }
        tpm.settle(rateLimiter, logRow.getTotalTokens());
        saveLog(logRow, start);
    }

    // ---------- embeddings / models ----------

    /** /v1/embeddings 透传(非流式),计量按输入文本粗估 */
    public JsonNode embeddings(CurrentUser user, ObjectNode payload, String channelKey) {
        String model = payload.path("model").asText("");
        if (model.isBlank()) {
            throw BizException.badRequest("请求体缺少 model 字段");
        }
        ChannelEntity channel = selectChannel(user, model, channelKey);
        // embedding 无输出 token,预扣成本就是输入文本估算
        TpmReservation tpm = reserveTpm(channel, user, estimateTokens(payload.path("input").toString()));

        long start = System.currentTimeMillis();
        InvokeLogEntity logRow = newLogRow(user, channel, model);
        try {
            JsonNode resp = ChannelAuth.apply(restClient.post()
                    .uri(ChannelAuth.authUri(channel.getBaseUrl() + "/embeddings", channel))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload), channel)
                    .retrieve()
                    .body(JsonNode.class);
            int tokens = resp == null ? 0 : resp.path("usage").path("total_tokens").asInt(0);
            if (tokens == 0) {
                tokens = estimateTokens(payload.path("input").toString());
            }
            logRow.setPromptTokens(tokens);
            logRow.setCompletionTokens(0);
            logRow.setTotalTokens(tokens);
            logRow.setStatus(1);
            recordCircuit(channel, true);
            tpm.settle(rateLimiter, tokens);
            return resp;
        } catch (Exception e) {
            tpm.release(rateLimiter);
            logRow.setStatus(0);
            logRow.setErrorMessage(truncate(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
            recordCircuit(channel, false);
            throw BizException.badRequest("Embedding 调用失败: " + e.getMessage());
        } finally {
            saveLog(logRow, start);
        }
    }

    /**
     * /v1/models: 指定渠道时透传上游 /models;未指定时按本地渠道配置聚合,
     * 输出 OpenAI 兼容的模型列表。
     */
    public JsonNode listModels(String channelKey) {
        if (channelKey != null && !channelKey.isBlank()) {
            ChannelEntity channel = channelService.findEnabledByKey(channelKey);
            try {
                return ChannelAuth.apply(restClient.get()
                        .uri(ChannelAuth.authUri(channel.getBaseUrl() + "/models", channel)), channel)
                        .retrieve()
                        .body(JsonNode.class);
            } catch (Exception e) {
                throw BizException.badRequest("查询模型列表失败 [" + channel.getName() + "]: " + e.getMessage());
            }
        }
        ObjectNode result = mapper.createObjectNode();
        result.put("object", "list");
        ArrayNode data = result.putArray("data");
        for (ChannelEntity c : channelService.listEnabled()) {
            for (String m : ChannelService.parseModels(c.getModels())) {
                ObjectNode node = data.addObject();
                node.put("id", m);
                node.put("object", "model");
                node.put("owned_by", c.getProvider());
            }
        }
        return result;
    }

    // ---------- 内部: 渠道调度与限流 ----------

    private String requireModel(ObjectNode payload) {
        String model = payload.path("model").asText("");
        if (model.isBlank()) {
            throw BizException.badRequest("请求体缺少 model 字段");
        }
        return model;
    }

    /** 全局 + 用户维度限流 -> 选渠道(跳过熔断) -> 渠道维度限流 */
    private ChannelEntity selectChannel(CurrentUser user, String model, String channelKey) {
        for (PolicyEntity policy : policyService.rateLimitPolicies()) {
            switch (policy.getTargetType()) {
                case PolicyEntity.TARGET_GLOBAL -> rateLimiter.acquireOrThrow(policy, null);
                case PolicyEntity.TARGET_USER -> {
                    if (policy.getTargetKey() == null || policy.getTargetKey().equals(user.username())) {
                        rateLimiter.acquireOrThrow(policy, user.username());
                    }
                }
                default -> { /* CHANNEL 维度在选定渠道后判定 */ }
            }
        }

        ChannelEntity channel;
        if (channelKey != null && !channelKey.isBlank()) {
            channel = channelService.findEnabledByKey(channelKey);
            if (isCircuitOpen(channel)) {
                throw BizException.badRequest("渠道[" + channel.getName() + "]已熔断,请稍后重试");
            }
            if (!ChannelService.parseModels(channel.getModels()).contains(model)) {
                log.warn("渠道[{}]的模型列表未声明[{}],仍按指定渠道转发", channelKey, model);
            }
        } else {
            List<ChannelEntity> candidates = channelService.findForModel(model).stream()
                    .filter(c -> !isCircuitOpen(c))
                    .toList();
            if (candidates.isEmpty()) {
                throw BizException.notFound("没有可用渠道支持模型[" + model + "](可能已熔断或未配置)");
            }
            channel = candidates.getFirst();
        }

        for (PolicyEntity policy : policyService.rateLimitPolicies()) {
            if (PolicyEntity.TARGET_CHANNEL.equals(policy.getTargetType())
                    && (policy.getTargetKey() == null || policy.getTargetKey().equals(channel.getId()))) {
                rateLimiter.acquireOrThrow(policy, channel.getId());
            }
        }
        return channel;
    }

    private InvokeLogEntity newLogRow(CurrentUser user, ChannelEntity channel, String model) {
        InvokeLogEntity logRow = new InvokeLogEntity();
        logRow.setUserId(user.userId());
        logRow.setUsername(user.username());
        logRow.setChannelId(channel.getId());
        logRow.setChannelName(channel.getName());
        logRow.setModel(model);
        // 全链路请求 ID(RequestIdFilter 已放入 MDC),与 NestJS/ai-service 日志按 id 关联
        logRow.setRequestId(org.slf4j.MDC.get("requestId"));
        return logRow;
    }

    private void saveLog(InvokeLogEntity logRow, long start) {
        logRow.setDurationMs(System.currentTimeMillis() - start);
        logRow.setCreatedAt(LocalDateTime.now());
        logRepository.save(logRow);
    }

    private boolean isCircuitOpen(ChannelEntity channel) {
        for (PolicyEntity policy : policyService.circuitBreakerPolicies()) {
            if (PolicyEntity.TARGET_CHANNEL.equals(policy.getTargetType())
                    && policy.getTargetKey() != null && !policy.getTargetKey().equals(channel.getId())) {
                continue;
            }
            if (circuitBreaker.isOpen(policy, channel.getId())) {
                return true;
            }
        }
        return false;
    }

    private void recordCircuit(ChannelEntity channel, boolean success) {
        for (PolicyEntity policy : policyService.circuitBreakerPolicies()) {
            if (PolicyEntity.TARGET_CHANNEL.equals(policy.getTargetType())
                    && policy.getTargetKey() != null && !policy.getTargetKey().equals(channel.getId())) {
                continue;
            }
            if (success) {
                circuitBreaker.recordSuccess(policy, channel.getId());
            } else {
                circuitBreaker.recordFailure(policy, channel.getId());
            }
        }
    }

    // ---------- 内部: TPM 预扣 / 结算(两段式) ----------

    /** TPM 预扣凭证: 记录本次请求在哪些策略桶预扣了多少,成功后按真实用量结算(多退少补),失败全额退还 */
    private static final class TpmReservation {
        private record Entry(PolicyEntity policy, String targetKey) {}

        private final List<Entry> entries = new ArrayList<>();
        private final long reserved;

        TpmReservation(long reserved) {
            this.reserved = reserved;
        }

        void add(PolicyEntity policy, String targetKey) {
            entries.add(new Entry(policy, targetKey));
        }

        /** 成功结算: 实际 < 预扣退差额;实际 > 预扣补扣(允许欠费) */
        void settle(RateLimiter rateLimiter, long actualTokens) {
            for (Entry e : entries) {
                if (actualTokens < reserved) {
                    rateLimiter.refundTpm(e.policy(), e.targetKey(), reserved - actualTokens);
                } else if (actualTokens > reserved) {
                    rateLimiter.consumeTpmAllowDebt(e.policy(), e.targetKey(), actualTokens - reserved);
                }
            }
        }

        /** 失败退还全部预扣 */
        void release(RateLimiter rateLimiter) {
            for (Entry e : entries) {
                rateLimiter.refundTpm(e.policy(), e.targetKey(), reserved);
            }
        }
    }

    /**
     * 转发前预扣 TPM: 任一 TPM 策略预扣失败时退还已扣部分并抛 429,请求不发往上游。
     * 定向策略(targetKey 指定的用户/渠道)只对匹配对象生效。
     */
    private TpmReservation reserveTpm(ChannelEntity channel, CurrentUser user, long estimatedTokens) {
        TpmReservation reservation = new TpmReservation(Math.max(estimatedTokens, 0));
        if (estimatedTokens <= 0) {
            return reservation;
        }
        for (PolicyEntity policy : policyService.rateLimitPolicies()) {
            if (policy.getTpm() == null || policy.getTpm() <= 0 || !matchesTpmTarget(policy, channel, user)) {
                continue;
            }
            String targetKey = tpmTargetKey(policy, channel, user);
            try {
                rateLimiter.acquireTpmOrThrow(policy, targetKey, estimatedTokens);
            } catch (BizException e) {
                reservation.release(rateLimiter);
                throw e;
            }
            reservation.add(policy, targetKey);
        }
        return reservation;
    }

    private boolean matchesTpmTarget(PolicyEntity policy, ChannelEntity channel, CurrentUser user) {
        return switch (policy.getTargetType()) {
            case PolicyEntity.TARGET_USER ->
                    policy.getTargetKey() == null || policy.getTargetKey().equals(user.username());
            case PolicyEntity.TARGET_CHANNEL ->
                    policy.getTargetKey() == null || policy.getTargetKey().equals(channel.getId());
            default -> true; // GLOBAL 恒生效
        };
    }

    private String tpmTargetKey(PolicyEntity policy, ChannelEntity channel, CurrentUser user) {
        return switch (policy.getTargetType()) {
            case PolicyEntity.TARGET_USER -> user.username();
            case PolicyEntity.TARGET_CHANNEL -> channel.getId();
            default -> null;
        };
    }

    /** 预扣成本估算: prompt 粗估 + max_tokens/max_completion_tokens(缺省按 4096 保守估) */
    private long estimateRequestTokens(ObjectNode body) {
        long prompt = estimateTokens(body.path("messages").toString());
        long maxOut = 4096;
        if (body.path("max_tokens").isNumber()) {
            maxOut = body.path("max_tokens").asLong();
        } else if (body.path("max_completion_tokens").isNumber()) {
            maxOut = body.path("max_completion_tokens").asLong();
        }
        return prompt + maxOut;
    }

    // ---------- 内部: 流末计量 ----------

    private static final Pattern USAGE_PROMPT = Pattern.compile("\"prompt_tokens\"\\s*:\\s*(\\d+)");
    private static final Pattern USAGE_COMPLETION = Pattern.compile("\"completion_tokens\"\\s*:\\s*(\\d+)");

    /** 从 SSE 尾部文本提取最后一个 usage 块的 prompt/completion tokens */
    private int[] parseStreamUsage(StringBuilder tail) {
        int usageIdx = tail.lastIndexOf("\"usage\"");
        if (usageIdx < 0) {
            return new int[]{0, 0};
        }
        String slice = tail.substring(usageIdx);
        Matcher pm = USAGE_PROMPT.matcher(slice);
        Matcher cm = USAGE_COMPLETION.matcher(slice);
        int prompt = pm.find() ? Integer.parseInt(pm.group(1)) : 0;
        int completion = cm.find() ? Integer.parseInt(cm.group(1)) : 0;
        return new int[]{prompt, completion};
    }

    /** 粗估完成 token 时去掉 SSE 信封,只留正文近似文本 */
    private String stripSseEnvelope(String tail) {
        return tail.replace("data:", "").replace("\"delta\"", "");
    }

    private void appendCapped(StringBuilder sb, String chunk, int cap) {
        sb.append(chunk);
        if (sb.length() > cap) {
            sb.delete(0, sb.length() - cap);
        }
    }

    private String truncate(String s) {
        return s == null ? null : s.substring(0, Math.min(2000, s.length()));
    }

    /** 粗略估算: 英文约 4 字符/token,中文按 1.5 字符/token 折算 */
    private int estimateTokens(String text) {
        if (text == null || text.isEmpty()) {
            return 0;
        }
        long cjk = text.codePoints().filter(c -> c > 0x2E7F).count();
        return (int) Math.ceil(cjk / 1.5 + (text.length() - cjk) / 4.0);
    }
}
