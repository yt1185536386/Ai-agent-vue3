package com.v3agent.rag.search;

import com.v3agent.rag.auth.AuthContext;
import com.v3agent.rag.chat.EmbeddingClient;
import com.v3agent.rag.kb.KnowledgeBaseService;
import com.v3agent.rag.vector.ChunkData;
import com.v3agent.rag.vector.VectorStore;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 检索原语：embed 问题 → 按知识库（或用户全部知识库）向量检索 Top-K，返回片段。
 * 与 {@code RagChatService} 的区别：只返回检索片段，不拼 prompt、不调模型，
 * 供 ai-service 等外部消费方自行编排（Agent 拿到片段自行决策）。
 */
@Service
@RequiredArgsConstructor
public class SearchService {

    private final KnowledgeBaseService kbService;
    private final VectorStore vectorStore;
    private final EmbeddingClient embeddingClient;

    @Value("${rag.retrieval.top-k:5}")
    private int defaultTopK;

    public List<SearchHit> search(SearchRequest req) {
        var user = AuthContext.require();
        int topK = req.topK() != null ? req.topK() : defaultTopK;

        // 确定待检索的知识库集合：指定单个，或当前用户拥有的全部
        List<String> kbIds;
        if (req.knowledgeBaseId() != null && !req.knowledgeBaseId().isBlank()) {
            kbService.getMine(req.knowledgeBaseId()); // 归属校验
            kbIds = List.of(req.knowledgeBaseId());
        } else {
            kbIds = kbService.listMine().stream()
                    .map(kb -> kb.getId())
                    .collect(Collectors.toList());
        }

        float[] questionVector = embeddingClient.embed(req.question(), user.userId(), user.username());

        // 跨知识库检索后合并，统一按 L2 距离升序取 topK
        List<SearchHit> hits = new ArrayList<>();
        for (String kbId : kbIds) {
            for (ChunkData c : vectorStore.search(kbId, questionVector, topK)) {
                hits.add(new SearchHit(c.id(), c.documentId(), c.chunkIndex(),
                        c.content(), l2Distance(questionVector, c.embedding())));
            }
        }
        hits.sort(Comparator.comparingDouble(SearchHit::distance));
        return hits.stream().limit(topK).toList();
    }

    private double l2Distance(float[] a, float[] b) {
        if (a == null || b == null || a.length != b.length) {
            return Double.MAX_VALUE;
        }
        double sum = 0;
        for (int i = 0; i < a.length; i++) {
            double diff = a[i] - b[i];
            sum += diff * diff;
        }
        return Math.sqrt(sum);
    }
}