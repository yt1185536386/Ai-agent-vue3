package com.v3agent.rag.chat;

import com.v3agent.rag.common.BizException;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Locale;

/**
 * 根据 model-gateway 中配置的渠道模型列表，自动解析 embedding 模型和 chat 模型。
 * 规则：
 * - 模型名包含 "embedding" 视为 embedding 模型
 * - 其余模型中，优先取包含 qwen/gpt/llama/claude 的模型作为 chat 模型
 * 如果解析失败，退回到 application.yml 中配置的硬编码模型名。
 */
@Slf4j
@Component
public class ModelResolver {

    private final ChannelInfoClient channelInfoClient;
    private final String channelKey;
    private final String fallbackEmbeddingModel;
    private final String fallbackChatModel;

    private volatile ResolvedModels resolved;

    public ModelResolver(ChannelInfoClient channelInfoClient,
                         @Value("${rag.model.channel-key:}") String channelKey,
                         @Value("${rag.model.embedding-model:text-embedding-3-small}") String fallbackEmbeddingModel,
                         @Value("${rag.model.chat-model:gpt-4o-mini}") String fallbackChatModel) {
        this.channelInfoClient = channelInfoClient;
        this.channelKey = channelKey;
        this.fallbackEmbeddingModel = fallbackEmbeddingModel;
        this.fallbackChatModel = fallbackChatModel;
    }

    @PostConstruct
    public void init() {
        if (channelKey == null || channelKey.isBlank()) {
            log.info("未配置 rag.model.channel-key，使用硬编码模型: embedding={}, chat={}",
                    fallbackEmbeddingModel, fallbackChatModel);
            this.resolved = new ResolvedModels(fallbackEmbeddingModel, fallbackChatModel);
            return;
        }
        this.resolved = resolveFromChannel();
    }

    public String getEmbeddingModel() {
        return resolved.embeddingModel();
    }

    public String getChatModel() {
        return resolved.chatModel();
    }

    /**
     * 强制重新从 model-gateway 拉取渠道模型列表并解析。
     * 可用于渠道变更后刷新，无需重启 rag-service。
     */
    public synchronized void refresh() {
        if (channelKey == null || channelKey.isBlank()) {
            return;
        }
        this.resolved = resolveFromChannel();
    }

    private ResolvedModels resolveFromChannel() {
        try {
            ChannelInfoClient.ChannelInfo info = channelInfoClient.fetch(channelKey);
            List<String> models = info.models();
            if (models == null || models.isEmpty()) {
                log.warn("渠道 {} 没有配置模型，回退到硬编码", channelKey);
                return new ResolvedModels(fallbackEmbeddingModel, fallbackChatModel);
            }

            String embedding = models.stream()
                    .filter(m -> m.toLowerCase(Locale.ROOT).contains("embedding"))
                    .findFirst()
                    .orElse(fallbackEmbeddingModel);

            String chat = models.stream()
                    .filter(m -> !m.equalsIgnoreCase(embedding))
                    .filter(m -> {
                        String lower = m.toLowerCase(Locale.ROOT);
                        return lower.contains("qwen") || lower.contains("gpt") || lower.contains("llama") || lower.contains("claude");
                    })
                    .findFirst()
                    .orElseGet(() -> models.stream()
                            .filter(m -> !m.equalsIgnoreCase(embedding))
                            .findFirst()
                            .orElse(fallbackChatModel));

            log.info("从渠道 {} 解析模型: embedding={}, chat={}", channelKey, embedding, chat);
            return new ResolvedModels(embedding, chat);
        } catch (BizException e) {
            log.warn("从渠道 {} 解析模型失败: {}，回退到硬编码", channelKey, e.getMessage());
            return new ResolvedModels(fallbackEmbeddingModel, fallbackChatModel);
        } catch (Exception e) {
            log.error("从渠道 {} 解析模型异常", channelKey, e);
            return new ResolvedModels(fallbackEmbeddingModel, fallbackChatModel);
        }
    }

    public record ResolvedModels(String embeddingModel, String chatModel) {}
}
