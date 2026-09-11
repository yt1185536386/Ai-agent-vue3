package com.v3agent.rag.chat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.v3agent.rag.common.BizException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * 调用 model-gateway /v1/chat/completions 进行对话。
 */
@Slf4j
@Component
public class ChatClient {

    private final RestClient restClient;
    private final String serviceKey;
    private final ModelResolver modelResolver;
    private final ObjectMapper mapper = new ObjectMapper();

    public ChatClient(RestClient gatewayRestClient,
                      @Value("${rag.gateway.service-key}") String serviceKey,
                      ModelResolver modelResolver) {
        this.restClient = gatewayRestClient;
        this.serviceKey = serviceKey;
        this.modelResolver = modelResolver;
    }

    /**
     * 非流式对话。
     *
     * @param messages  OpenAI 兼容 messages 列表
     * @param userId    用户 ID（透传给网关做计量）
     * @param username  用户名（透传给网关做计量）
     * @return 模型回答文本
     */
    public String chat(List<Map<String, String>> messages, String userId, String username) {
        if (serviceKey == null || serviceKey.isBlank()) {
            throw BizException.badRequest("未配置 rag.gateway.service-key，无法调用模型网关");
        }

        ObjectNode body = mapper.createObjectNode();
        body.put("model", modelResolver.getChatModel());
        ArrayNode msgs = body.putArray("messages");
        for (Map<String, String> m : messages) {
            ObjectNode node = msgs.addObject();
            node.put("role", m.getOrDefault("role", "user"));
            node.put("content", m.getOrDefault("content", ""));
        }

        JsonNode resp;
        try {
            resp = restClient.post()
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer " + serviceKey)
                    .header("X-User-Id", userId)
                    .header("X-Username", encode(username))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (Exception e) {
            log.error("调用模型网关 /v1/chat/completions 失败", e);
            throw BizException.badRequest("模型调用失败: " + e.getMessage());
        }

        if (resp == null || !resp.has("choices") || !resp.path("choices").isArray()) {
            throw BizException.badRequest("模型响应格式异常: 缺少 choices");
        }

        JsonNode choices = resp.path("choices");
        if (choices.isEmpty()) {
            throw BizException.badRequest("模型响应为空");
        }

        String content = choices.get(0).path("message").path("content").asText(null);
        if (content == null) {
            throw BizException.badRequest("模型响应格式异常: 缺少 content");
        }
        return content;
    }

    private String encode(String s) {
        if (s == null) {
            return "";
        }
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }
}
