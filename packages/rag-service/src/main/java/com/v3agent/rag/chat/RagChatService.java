package com.v3agent.rag.chat;

import com.v3agent.rag.auth.AuthContext;
import com.v3agent.rag.common.BizException;
import com.v3agent.rag.kb.KnowledgeBaseService;
import com.v3agent.rag.vector.ChunkData;
import com.v3agent.rag.vector.VectorStore;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * RAG 问答核心流程： embed 问题 → 向量检索 Top-K → 拼 prompt → chat → 返回。
 */
@Service
@RequiredArgsConstructor
public class RagChatService {

    private final KnowledgeBaseService kbService;
    private final VectorStore vectorStore;
    private final EmbeddingClient embeddingClient;
    private final ChatClient chatClient;

    @Value("${rag.retrieval.top-k:5}")
    private int topK;

    public ChatResponse ask(String knowledgeBaseId, String question) {
        // 1. 校验知识库归属
        kbService.getMine(knowledgeBaseId);
        var currentUser = AuthContext.require();

        // 2. 把问题转成向量
        float[] questionVector = embeddingClient.embed(question, currentUser.userId(), currentUser.username());

        // 3. 从向量存储检索 Top-K
        List<ChunkData> chunks = vectorStore.search(knowledgeBaseId, questionVector, topK);
        if (chunks.isEmpty()) {
            return new ChatResponse(
                    "知识库中暂无相关文档，无法回答问题。",
                    List.of()
            );
        }

        // 4. 拼上下文
        String context = chunks.stream()
                .map(ChunkData::content)
                .collect(Collectors.joining("\n---\n"));

        String systemPrompt = """
                你是一个严谨的智能助手。请严格根据以下上下文回答用户问题。
                如果上下文不足以回答问题，请明确说明“根据提供的资料无法回答”。
                不要编造上下文之外的信息。

                上下文：
                %s
                """.formatted(context);

        List<Map<String, String>> messages = List.of(
                Map.of("role", "system", "content", systemPrompt),
                Map.of("role", "user", "content", question)
        );

        // 5. 调用模型网关对话
        String answer = chatClient.chat(messages, currentUser.userId(), currentUser.username());

        List<String> references = chunks.stream()
                .map(c -> "[片段 " + c.chunkIndex() + "] " + c.content())
                .toList();

        return new ChatResponse(answer, references);
    }
}
