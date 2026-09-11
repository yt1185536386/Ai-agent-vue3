package com.v3agent.rag.vector;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 内存版向量存储实现，用于无 PostgreSQL/pgvector 的本地快速启动与测试。
 * 按 L2 距离排序，重启后数据丢失。
 */
@Component
@Profile("!pgvector")
public class InMemoryVectorStore implements VectorStore {

    private final Map<String, List<ChunkData>> chunksByDocumentId = new ConcurrentHashMap<>();

    @Override
    public void saveChunks(String documentId, String knowledgeBaseId, List<ChunkData> chunks) {
        List<ChunkData> saved = chunks.stream()
                .map(chunk -> new ChunkData(
                        chunk.id() == null ? UUID.randomUUID().toString() : chunk.id(),
                        documentId,
                        knowledgeBaseId,
                        chunk.chunkIndex(),
                        chunk.content(),
                        chunk.embedding()
                ))
                .toList();
        chunksByDocumentId.merge(documentId, new ArrayList<>(saved), (oldList, newList) -> {
            oldList.addAll(newList);
            return oldList;
        });
    }

    @Override
    public void deleteByDocumentId(String documentId) {
        chunksByDocumentId.remove(documentId);
    }

    @Override
    public List<ChunkData> search(String knowledgeBaseId, float[] queryVector, int topK) {
        return chunksByDocumentId.values().stream()
                .flatMap(List::stream)
                .filter(chunk -> chunk.knowledgeBaseId().equals(knowledgeBaseId))
                .sorted(Comparator.comparingDouble(chunk -> l2Distance(queryVector, chunk.embedding())))
                .limit(topK)
                .toList();
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
