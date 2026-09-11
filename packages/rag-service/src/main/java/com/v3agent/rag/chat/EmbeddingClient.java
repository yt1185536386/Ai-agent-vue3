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
import java.util.ArrayList;
import java.util.List;

/**
 * 调用 model-gateway /v1/embeddings，把文本转为向量。
 */
@Slf4j
@Component
public class EmbeddingClient {

    private final RestClient restClient;
    private final String serviceKey;
    private final ModelResolver modelResolver;
    private final ObjectMapper mapper = new ObjectMapper();

    public EmbeddingClient(RestClient gatewayRestClient,
                           @Value("${rag.gateway.service-key}") String serviceKey,
                           ModelResolver modelResolver) {
        this.restClient = gatewayRestClient;
        this.serviceKey = serviceKey;
        this.modelResolver = modelResolver;
    }

    /**
     * 对单段文本进行 Embedding。
     *
     * @param text     待嵌入文本
     * @param userId   用户 ID（透传给网关做计量）
     * @param username 用户名（透传给网关做计量）
     * @return 向量数组
     */
    public float[] embed(String text, String userId, String username) {
        if (serviceKey == null || serviceKey.isBlank()) {
            throw BizException.badRequest("未配置 rag.gateway.service-key，无法调用模型网关");
        }

        ObjectNode body = mapper.createObjectNode();
        body.put("model", modelResolver.getEmbeddingModel());
        body.put("input", text);

        JsonNode resp;
        try {
            resp = restClient.post()
                    .uri("/v1/embeddings")
                    .header("Authorization", "Bearer " + serviceKey)
                    .header("X-User-Id", userId)
                    .header("X-Username", encode(username))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (Exception e) {
            log.error("调用模型网关 /v1/embeddings 失败", e);
            throw BizException.badRequest("Embedding 调用失败: " + e.getMessage());
        }

        if (resp == null || !resp.has("data") || !resp.path("data").isArray()) {
            throw BizException.badRequest("Embedding 响应格式异常: 缺少 data 数组");
        }

        ArrayNode data = (ArrayNode) resp.path("data");
        if (data.isEmpty()) {
            throw BizException.badRequest("Embedding 响应为空");
        }

        JsonNode embeddingNode = data.get(0).path("embedding");
        if (!embeddingNode.isArray()) {
            throw BizException.badRequest("Embedding 响应格式异常: 缺少 embedding 数组");
        }

        float[] vector = new float[embeddingNode.size()];
        for (int i = 0; i < embeddingNode.size(); i++) {
            vector[i] = (float) embeddingNode.get(i).asDouble();
        }
        return vector;
    }

    /**
     * 批量嵌入文本列表。
     */
    public List<float[]> embedBatch(List<String> texts, String userId, String username) {
        if (serviceKey == null || serviceKey.isBlank()) {
            throw BizException.badRequest("未配置 rag.gateway.service-key，无法调用模型网关");
        }

        ObjectNode body = mapper.createObjectNode();
        body.put("model", modelResolver.getEmbeddingModel());
        ArrayNode inputs = body.putArray("input");
        texts.forEach(inputs::add);

        JsonNode resp;
        try {
            resp = restClient.post()
                    .uri("/v1/embeddings")
                    .header("Authorization", "Bearer " + serviceKey)
                    .header("X-User-Id", userId)
                    .header("X-Username", encode(username))
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (Exception e) {
            log.error("调用模型网关 /v1/embeddings 失败", e);
            throw BizException.badRequest("Embedding 批量调用失败: " + e.getMessage());
        }

        if (resp == null || !resp.has("data") || !resp.path("data").isArray()) {
            throw BizException.badRequest("Embedding 响应格式异常: 缺少 data 数组");
        }

        ArrayNode data = (ArrayNode) resp.path("data");
        if (data.size() != texts.size()) {
            throw BizException.badRequest("Embedding 批量响应数量不匹配: 请求 " + texts.size() + ", 返回 " + data.size());
        }

        List<float[]> result = new ArrayList<>(data.size());
        for (int i = 0; i < data.size(); i++) {
            JsonNode embeddingNode = data.get(i).path("embedding");
            float[] vector = new float[embeddingNode.size()];
            for (int j = 0; j < embeddingNode.size(); j++) {
                vector[j] = (float) embeddingNode.get(j).asDouble();
            }
            result.add(vector);
        }
        return result;
    }

    private String encode(String s) {
        if (s == null) {
            return "";
        }
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }
}
