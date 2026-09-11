package com.v3agent.gateway.repo;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.v3agent.gateway.common.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ChannelService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final ChannelRepository channelRepository;

    public List<ChannelEntity> listAll() {
        return channelRepository.findAll().stream()
                .sorted(Comparator.comparing(ChannelEntity::getPriority))
                .toList();
    }

    public ChannelEntity findById(String id) {
        return channelRepository.findById(id)
                .orElseThrow(() -> BizException.notFound("渠道不存在"));
    }

    /** 启用的渠道,按优先级排序(模型调用调度用) */
    public List<ChannelEntity> listEnabled() {
        return channelRepository.findByStatusOrderByPriorityAsc(1);
    }

    /** 找出支持指定模型的启用渠道 */
    public List<ChannelEntity> findForModel(String model) {
        return listEnabled().stream()
                .filter(c -> parseModels(c.getModels()).contains(model))
                .toList();
    }

    /** 按渠道 key 查找(X-Channel-Key 头指定),要求渠道启用 */
    public ChannelEntity findEnabledByKey(String channelKey) {
        ChannelEntity c = channelRepository.findByChannelKey(channelKey)
                .orElseThrow(() -> BizException.notFound("渠道不存在: " + channelKey));
        if (!Integer.valueOf(1).equals(c.getStatus())) {
            throw BizException.badRequest("渠道已禁用: " + channelKey);
        }
        return c;
    }

    @Transactional
    public ChannelEntity create(ChannelRequest req) {
        ChannelEntity c = new ChannelEntity();
        apply(c, req);
        return channelRepository.save(c);
    }

    @Transactional
    public ChannelEntity update(String id, ChannelRequest req) {
        ChannelEntity c = findById(id);
        apply(c, req);
        return channelRepository.save(c);
    }

    @Transactional
    public ChannelEntity changeStatus(String id, int status) {
        ChannelEntity c = findById(id);
        c.setStatus(status);
        return channelRepository.save(c);
    }

    @Transactional
    public void delete(String id) {
        channelRepository.delete(findById(id));
    }

    private void apply(ChannelEntity c, ChannelRequest req) {
        c.setName(req.name());
        c.setChannelKey(req.channelKey() == null || req.channelKey().isBlank() ? null : req.channelKey().trim());
        c.setProvider(req.provider());
        c.setUpstreamFormat(req.upstreamFormat() == null || req.upstreamFormat().isBlank()
                ? "openai" : req.upstreamFormat().trim());
        c.setAuthType(req.authType() == null || req.authType().isBlank()
                ? ChannelAuth.BEARER : req.authType().trim());
        c.setBaseUrl(req.baseUrl().replaceAll("/+$", ""));
        c.setApiKey(req.apiKey());
        c.setModels(writeModels(req.models()));
        c.setEnableSearch(Boolean.TRUE.equals(req.enableSearch()));
        c.setSupportsTools(Boolean.TRUE.equals(req.supportsTools()));
        c.setPriority(req.priority() == null ? 10 : req.priority());
        c.setStatus(req.status() == null ? 1 : req.status());
        c.setRemark(req.remark());
    }

    public static List<String> parseModels(String json) {
        try {
            return MAPPER.readValue(json, new TypeReference<>() {});
        } catch (Exception e) {
            return List.of();
        }
    }

    /**
     * 真实调用上游 GET {baseUrl}/models 拉取模型列表(OpenAI 兼容格式)。
     * 按给定认证字段附 API Key;上游非 2xx / 返回格式不符时抛出带原因的业务异常。
     */
    public List<String> fetchModels(String baseUrl, String apiKey, String authType) {
        ChannelEntity probe = new ChannelEntity();
        probe.setBaseUrl(baseUrl.replaceAll("/+$", ""));
        probe.setApiKey(apiKey);
        probe.setAuthType(authType);
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(8));
        factory.setReadTimeout(Duration.ofSeconds(15));
        RestClient client = RestClient.builder().requestFactory(factory).build();
        JsonNode resp;
        try {
            resp = ChannelAuth.apply(client.get().uri(ChannelAuth.authUri(probe.getBaseUrl() + "/models", probe)), probe)
                    .retrieve()
                    .body(JsonNode.class);
        } catch (Exception e) {
            throw BizException.badRequest("调用上游模型列表失败: " + e.getMessage());
        }
        List<String> models = new ArrayList<>();
        if (resp != null && resp.path("data").isArray()) {
            for (JsonNode m : resp.path("data")) {
                String id = m.path("id").asText(null);
                if (id != null && !id.isBlank()) {
                    models.add(id);
                }
            }
        }
        if (models.isEmpty()) {
            throw BizException.badRequest("上游未返回 OpenAI 兼容的模型列表(data[].id)");
        }
        return models;
    }

    private static String writeModels(List<String> models) {
        try {
            return MAPPER.writeValueAsString(models);
        } catch (Exception e) {
            throw BizException.badRequest("模型列表格式错误");
        }
    }
}
