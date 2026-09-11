package com.v3agent.rag.chat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.v3agent.rag.common.ApiResponse;
import com.v3agent.rag.common.BizException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 调用 model-gateway 的内部接口 /v1/channels/{channelKey} 获取渠道模型列表。
 */
@Slf4j
@Component
public class ChannelInfoClient {

    private final RestClient restClient;
    private final String serviceKey;
    private final ObjectMapper mapper = new ObjectMapper();

    public ChannelInfoClient(RestClient gatewayRestClient,
                             @Value("${rag.gateway.service-key}") String serviceKey) {
        this.restClient = gatewayRestClient;
        this.serviceKey = serviceKey;
    }

    public ChannelInfo fetch(String channelKey) {
        if (serviceKey == null || serviceKey.isBlank()) {
            throw BizException.badRequest("未配置 rag.gateway.service-key，无法调用模型网关");
        }

        JsonNode resp;
        try {
            resp = restClient.get()
                    .uri("/v1/channels/{channelKey}", channelKey)
                    .header("Authorization", "Bearer " + serviceKey)
                    .header("X-User-Id", "rag-service")
                    .header("X-Username", encode("rag-service"))
                    .accept(MediaType.APPLICATION_JSON)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (Exception e) {
            log.error("调用模型网关 /v1/channels/{} 失败", channelKey, e);
            throw BizException.badRequest("查询渠道失败: " + e.getMessage());
        }

        if (resp == null || !"0".equals(resp.path("errCode").asText())) {
            String errMsg = resp == null ? "响应为空" : resp.path("errMsg").asText("未知错误");
            throw BizException.badRequest("查询渠道失败: " + errMsg);
        }

        JsonNode data = resp.path("data");
        String key = data.path("channelKey").asText();
        List<String> models = new java.util.ArrayList<>();
        if (data.hasNonNull("models") && data.path("models").isArray()) {
            for (JsonNode node : data.path("models")) {
                models.add(node.asText());
            }
        }
        return new ChannelInfo(key, models);
    }

    public record ChannelInfo(String channelKey, List<String> models) {}

    private String encode(String s) {
        if (s == null) {
            return "";
        }
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }
}
